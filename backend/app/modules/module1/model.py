"""
Fine-tunes MiniLM to classify an account name into an account type.

What it does:
    Trains all-MiniLM-L6-v2 (mean pooling + dropout + linear layer) to predict
    account_type from account_name. Training stops early if test accuracy does
    not improve for 3 epochs, and the best epoch's weights are restored before
    the final report and saving.

Input (from the data-building script):
    data/train.csv, data/test.csv
    Required columns: account_name, account_type

Output:
    account_type_classifier/   (used by the inference pipeline)
        model_state_dict.pt    - best weights
        tokenizer files        - saved tokenizer
        label_classes.json     - class names, in label order
        config.json            - base model, hidden size, num_classes, max_len
    experiment_log.xlsx        - one row appended per run (settings, accuracy,
                                 macro/weighted F1, per-class F1 and support)
    Also prints the per-class classification report.

Settings (top of file): NUM_FROZEN_LAYERS, DROPOUT, EPOCHS.
    NUM_FROZEN_LAYERS is only logged for now, because the freezing code is
    commented out.

Note: the test set is used to pick the best epoch

Requirements: torch, transformers, scikit-learn, pandas, numpy, openpyxl.
    A GPU is recommended, but it also runs on CPU.
"""

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader
from transformers import AutoTokenizer, AutoModel
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import classification_report
import pandas as pd
import numpy as np
import random
import time
import os
import json
from datetime import datetime
import matplotlib.pyplot as plt   


# ---------------------------------------------------------
# Config for this run — change these between experiments
# ---------------------------------------------------------
NUM_FROZEN_LAYERS = 0
DROPOUT = 0.1
EPOCHS = 20

# ---------------------------------------------------------
# Reproducibility + device
# ---------------------------------------------------------
SEED = 42
random.seed(SEED)
np.random.seed(SEED)
torch.manual_seed(SEED)

device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
print("Using device:", device)

# ---------------------------------------------------------
# Early stopping setup
# ---------------------------------------------------------
PATIENCE = 3              # how many epochs to wait for improvement before stopping
best_test_acc = 0.0       # best accuracy seen so far (starts at 0 so epoch 1 always counts as an improvement)
epochs_no_improve = 0     # counter: epochs in a row with no improvement
best_state = None         # will hold a copy of the weights from the best epoch

# ---------------------------------------------------------
# Dataset — now uses account_type_label (int) instead of raw string labels
# ---------------------------------------------------------
class AccountNameDataset(Dataset):
    def __init__(self, df, tokenizer, max_len=32):
        self.names = df["account_name"].tolist()
        self.labels = df["account_type_label"].tolist()
        self.tokenizer = tokenizer
        self.max_len = max_len

    def __len__(self):
        return len(self.names)

    def __getitem__(self, idx):
        enc = self.tokenizer(
            self.names[idx],
            padding="max_length",
            truncation=True,
            max_length=self.max_len,
            return_tensors="pt",
        )
        return {
            "input_ids": enc["input_ids"].squeeze(0),
            "attention_mask": enc["attention_mask"].squeeze(0),
            "label": torch.tensor(self.labels[idx], dtype=torch.long),
        }

# ---------------------------------------------------------
# Model: MiniLM encoder + classification head (mean pooling)
# ---------------------------------------------------------
class AccountTypeClassifier(nn.Module):
    def __init__(self, base_model, hidden_size=384, num_classes=5):
        super().__init__()
        self.base_model = base_model
        self.dropout = nn.Dropout(DROPOUT)
        self.classifier = nn.Linear(hidden_size, num_classes)

    def forward(self, input_ids, attention_mask):
        outputs = self.base_model(input_ids=input_ids, attention_mask=attention_mask)
        pooled = mean_pool(outputs.last_hidden_state, attention_mask)
        pooled = self.dropout(pooled)
        return self.classifier(pooled)

def mean_pool(last_hidden_state, attention_mask):
    mask = attention_mask.unsqueeze(-1).expand(last_hidden_state.size()).float()
    summed = torch.sum(last_hidden_state * mask, dim=1)
    counts = torch.clamp(mask.sum(dim=1), min=1e-9)
    return summed / counts

# ---------------------------------------------------------
# Evaluation function
# ---------------------------------------------------------

def evaluate(model, loader):
    model.eval()
    correct, total = 0, 0
    all_preds, all_labels = [], []
    with torch.no_grad():
        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            attention_mask = batch["attention_mask"].to(device)
            labels = batch["label"].to(device)
            logits = model(input_ids, attention_mask)
            preds = torch.argmax(logits, dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)
            all_preds.extend(preds.cpu().tolist())
            all_labels.extend(labels.cpu().tolist())
    return correct / total, all_preds, all_labels

# ---------------------------------------------------------
# Log this run's config + metrics to a persistent Excel file
# ---------------------------------------------------------

def log_run_to_excel(
    frozen_layers,
    dropout,
    final_test_acc,
    test_preds,
    test_labels,
    type_encoder,
    excel_path="output/experiment_log.xlsx",
    extra_info=None,
):
    # Create the folder part of the path ("output") if it doesn't exist yet.
    # exist_ok=True means no error if the folder is already there.
    os.makedirs(os.path.dirname(excel_path), exist_ok=True)
    
    report_dict = classification_report(
        test_labels, test_preds,
        labels=list(range(len(type_encoder.classes_))),
        target_names=type_encoder.classes_,
        zero_division=0,
        output_dict=True,
    )

    row = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "frozen_layers": frozen_layers,
        "dropout": dropout,
        "test_accuracy": final_test_acc,
        "macro_precision": report_dict["macro avg"]["precision"],
        "macro_recall": report_dict["macro avg"]["recall"],
        "macro_f1": report_dict["macro avg"]["f1-score"],
        "weighted_precision": report_dict["weighted avg"]["precision"],
        "weighted_recall": report_dict["weighted avg"]["recall"],
        "weighted_f1": report_dict["weighted avg"]["f1-score"],
    }

    if extra_info:
        row.update(extra_info)

    # per-class F1 + support, so you can see exactly which classes
    # improve/degrade as you sweep frozen_layers / dropout
    for cls in type_encoder.classes_:
        row[f"f1_{cls}"] = report_dict[cls]["f1-score"]
        row[f"support_{cls}"] = report_dict[cls]["support"]

    new_row_df = pd.DataFrame([row])

    if os.path.exists(excel_path):
        existing_df = pd.read_excel(excel_path)
        combined_df = pd.concat([existing_df, new_row_df], ignore_index=True)
    else:
        combined_df = new_row_df

    combined_df.to_excel(excel_path, index=False)
    print(f"Logged run to {excel_path} (frozen_layers={frozen_layers}, dropout={dropout})")
    return combined_df

# ---------------------------------------------------------
# Load the combined train/test CSVs saved from notebook 1
# ---------------------------------------------------------
train_df = pd.read_csv("data/train.csv")
test_df = pd.read_csv("data/test.csv")

type_encoder = LabelEncoder().fit(pd.concat([train_df["account_type"], test_df["account_type"]]))
train_df["account_type_label"] = type_encoder.transform(train_df["account_type"])
test_df["account_type_label"] = type_encoder.transform(test_df["account_type"])

num_classes = len(type_encoder.classes_)
print("Classes:", list(type_encoder.classes_))

# ---------------------------------------------------------
# Tokenizer + base model
# ---------------------------------------------------------
# model_name = "sentence-transformers/all-MiniLM-L6-v2" # 68% acc, 22M parameters
model_name = "BAAI/bge-small-en-v1.5" # 88% acc, 33.4M params

tokenizer = AutoTokenizer.from_pretrained(model_name)
base_model = AutoModel.from_pretrained(model_name).to(device)

"""
# Freeze embeddings
for param in base_model.embeddings.parameters():
    param.requires_grad = False

# Freeze first of MiniLM's 6 encoder layers
for layer in base_model.encoder.layer[:(NUM_FROZEN_LAYERS-1)]:
    for param in layer.parameters():
        param.requires_grad = False
"""

# ---------------------------------------------------------
# Training
# ---------------------------------------------------------
train_dataset = AccountNameDataset(train_df, tokenizer)
test_dataset = AccountNameDataset(test_df, tokenizer)

train_loader = DataLoader(train_dataset, batch_size=16, shuffle=True)
test_loader = DataLoader(test_dataset, batch_size=16)

model = AccountTypeClassifier(base_model, num_classes=num_classes).to(device)
optimizer = torch.optim.AdamW(model.parameters(), lr=2e-5)
loss_fn = nn.CrossEntropyLoss()

train_acc_history = []   # will hold train accuracy of each epoch
test_acc_history = []    # will hold test accuracy of each epoch
for epoch in range(1, EPOCHS + 1):
    model.train()
    total_loss = 0
    for batch in train_loader:
        input_ids = batch["input_ids"].to(device)
        attention_mask = batch["attention_mask"].to(device)
        labels = batch["label"].to(device)

        optimizer.zero_grad()
        logits = model(input_ids, attention_mask)
        loss = loss_fn(logits, labels)
        loss.backward()
        optimizer.step()
        total_loss += loss.item()

    train_acc, _, _ = evaluate(model, train_loader)
    test_acc, _, _ = evaluate(model, test_loader)
    train_acc_history.append(train_acc)               # save this epoch's train accuracy
    test_acc_history.append(test_acc) 

    # --- Early stopping check (runs once per epoch, after evaluation) ---
    if test_acc > best_test_acc:
        best_test_acc = test_acc          # new best score
        epochs_no_improve = 0             # improvement happened, so reset the counter
        # copy the weights to CPU memory; clone() makes a real copy, not a reference
        best_state = {k: v.detach().cpu().clone() for k, v in model.state_dict().items()}
    else:
        epochs_no_improve += 1            # no improvement this epoch
        if epochs_no_improve >= PATIENCE:
            print(f"Early stopping at epoch {epoch} (best test_acc: {best_test_acc:.3f})")
            break                         # exit the epoch loop
    print(f"Epoch {epoch:2d} | loss: {total_loss/len(train_loader):.4f} | train_acc: {train_acc:.3f} | test_acc: {test_acc:.3f}")

# ---------------------------------------------------------
# Restore the best weights before final evaluation and saving
# ---------------------------------------------------------
if best_state is not None:                 # safety check: only restore if a best epoch was recorded
    model.load_state_dict(best_state)      # copies the best epoch's weights back into the model
    print(f"Restored best weights (test_acc: {best_test_acc:.3f})")
# Re-measure train accuracy on the restored best weights, so the log matches the saved model
best_train_acc, _, _ = evaluate(model, train_loader)   # evaluate() returns (accuracy, preds, labels); we only need accuracy

# plotting
# x-axis: epoch numbers 1, 2, 3, ... for however many epochs actually ran
# (fewer than EPOCHS if early stopping triggered)
epochs_ran = range(1, len(train_acc_history) + 1)

# Epoch with the highest test accuracy (argmax gives a 0-based index, so +1)
best_epoch = int(np.argmax(test_acc_history)) + 1

plt.figure(figsize=(8, 5))                                   # width x height in inches
plt.plot(epochs_ran, train_acc_history, marker="o", label="Train accuracy")   # blue line: train
plt.plot(epochs_ran, test_acc_history, marker="o", label="Test accuracy")     # orange line: test
plt.axvline(best_epoch, linestyle="--", color="gray", label=f"Best epoch ({best_epoch})")  # dashed line at the best epoch
plt.xlabel("Epoch")                                          # label under the x-axis
plt.ylabel("Accuracy")                                       # label beside the y-axis
plt.title("Train vs Test accuracy per epoch")                # plot title
plt.legend()                                                 # shows which line is which
plt.grid(alpha=0.3)                                          # faint grid to make values easier to read
plt.show()                                                   # displays the plot below the cell

# ---------------------------------------------------------
# Final test report (per-class — worth checking given class imbalance)
# ---------------------------------------------------------

start_time = time.time()

final_test_acc, test_preds, test_labels = evaluate(model, test_loader)

end_time = time.time()
duration = end_time - start_time

print(f"Evaluation Duration: {duration:.2f} seconds")
print(f"\nFinal test accuracy: {final_test_acc:.3f}\n")
print(classification_report(
    test_labels, test_preds,
    labels=list(range(num_classes)),
    target_names=type_encoder.classes_,
    zero_division=0,
))

log_run_to_excel(
    frozen_layers=NUM_FROZEN_LAYERS,
    dropout=DROPOUT,
    final_test_acc=final_test_acc,
    test_preds=test_preds,
    test_labels=test_labels,
    type_encoder=type_encoder,
    # min_instances=MIN_INSTANCES,   # set this to match the cutoff used when building train.csv/test.csv for this run
    extra_info={"epochs": EPOCHS, "lr": 2e-5, "train_acc_final": best_train_acc},
)

# ---------------------------------------------------------
# Save fine-tuned model + tokenizer + label encoder
# ---------------------------------------------------------
save_dir = "account_type_classifier"
os.makedirs(save_dir, exist_ok=True)

torch.save(model.state_dict(), os.path.join(save_dir, "model_state_dict.pt"))
tokenizer.save_pretrained(save_dir)

with open(os.path.join(save_dir, "label_classes.json"), "w") as f:
    json.dump(list(type_encoder.classes_), f)

with open(os.path.join(save_dir, "config.json"), "w") as f:
    json.dump({"base_model": model_name, "hidden_size": 384, "num_classes": num_classes, "max_len": 32}, f)

print(f"\nSaved model, tokenizer, and label classes to {save_dir}")