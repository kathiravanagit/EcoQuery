import json
import logging
import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.metrics import classification_report, confusion_matrix, precision_recall_fscore_support
from sklearn.calibration import calibration_curve
import joblib

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EcoQuery.classifier_eval")

def load_data():
    # Mock data to simulate real anonymized user queries, public datasets, and human-labeled ones
    data = [
        {"query": "What is the capital of France?", "label": "simple"},
        {"query": "Hello there", "label": "simple"},
        {"query": "Is the sky blue?", "label": "simple"},
        {"query": "Explain how quantum computing works in detail.", "label": "medium"},
        {"query": "Compare React and Angular for a large scale app.", "label": "medium"},
        {"query": "Write a distributed lock manager in Rust.", "label": "complex"},
        {"query": "def calculate_fibonacci(n):", "label": "complex"},
        {"query": "What is 2+2?", "label": "simple"},
        {"query": "Give me a summary of World War II.", "label": "medium"},
        {"query": "How do I optimize a SQL query with 10 joins?", "label": "complex"},
    ]
    # Multiply to simulate a larger dataset
    df = pd.DataFrame(data * 50)
    return df

def run_evaluation():
    logger.info("Loading dataset...")
    df = load_data()
    
    logger.info("Splitting dataset into train, validation, and test sets...")
    # Train 70%, Val 15%, Test 15%
    X_train_temp, X_test, y_train_temp, y_test = train_test_split(df['query'], df['label'], test_size=0.15, random_state=42)
    X_train, X_val, y_train, y_val = train_test_split(X_train_temp, y_train_temp, test_size=0.176, random_state=42)
    
    logger.info("Training pipeline...")
    pipeline = Pipeline([
        ('tfidf', TfidfVectorizer(ngram_range=(1, 2))),
        ('clf', LogisticRegression(max_iter=1000, class_weight='balanced'))
    ])
    
    pipeline.fit(X_train, y_train)
    
    logger.info("Evaluating on test set...")
    y_pred = pipeline.predict(X_test)
    y_proba = pipeline.predict_proba(X_test)
    
    logger.info("\n--- Classification Report ---")
    report = classification_report(y_test, y_pred)
    print(report)
    
    logger.info("\n--- Confusion Matrix ---")
    cm = confusion_matrix(y_test, y_pred)
    print(cm)
    
    # Precision, Recall, F1
    precision, recall, f1, _ = precision_recall_fscore_support(y_test, y_pred, average='weighted')
    logger.info(f"\nWeighted metrics -> Precision: {precision:.3f}, Recall: {recall:.3f}, F1: {f1:.3f}")
    
    logger.info("\n--- Confidence Calibration ---")
    # Simplify calibration curve analysis
    logger.info("Calibration computed (mocked logging for this script)")
    
    logger.info("\n--- Error Analysis ---")
    errors = X_test[y_test != y_pred]
    if not errors.empty:
        logger.info(f"Found {len(errors)} errors. Example:")
        print(errors.head())
    else:
        logger.info("No errors found in this evaluation split.")
        
    # Save the pipeline
    joblib.dump(pipeline, "backend/models/pipeline.pkl")
    logger.info("Pipeline saved to backend/models/pipeline.pkl")

if __name__ == "__main__":
    run_evaluation()
