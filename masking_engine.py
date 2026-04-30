import pandas as pd
import numpy as np
from presidio_analyzer import AnalyzerEngine, PatternRecognizer, Pattern
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from faker import Faker
import pyffx
import logging
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

fake = Faker('en_IN')

# FPE Setup
# For Aadhaar (12 digits), we use Integer FPE with an alphabet of '0123456789'
fpe_aadhaar = pyffx.String(b'blostem-secret-key', alphabet='0123456789', length=12)
# For PAN (10 chars: 5 letters, 4 numbers, 1 letter), pyffx doesn't easily support mixed format out of the box in one pass.
# Wait, pyffx string supports a custom alphabet. PAN has uppercase letters and numbers.
# We can just use String with alphabet of uppercase letters + numbers, length 10.
pan_alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789'
fpe_pan = pyffx.String(b'blostem-secret-key', alphabet=pan_alphabet, length=10)

def fpe_encrypt_pan(pan: str) -> str:
    if pd.isna(pan) or len(str(pan)) != 10: return pan
    return fpe_pan.encrypt(str(pan))

def fpe_encrypt_aadhaar(aadhaar: str) -> str:
    if pd.isna(aadhaar) or len(str(aadhaar)) != 12: return aadhaar
    return fpe_aadhaar.encrypt(str(aadhaar))

# Initialize engines
analyzer = AnalyzerEngine()
anonymizer = AnonymizerEngine()

# Custom Recognizers for India
pan_pattern = Pattern(name="pan_pattern", regex=r"[A-Z]{5}[0-9]{4}[A-Z]{1}", score=0.9)
pan_recognizer = PatternRecognizer(supported_entity="IN_PAN", patterns=[pan_pattern])
analyzer.registry.add_recognizer(pan_recognizer)

aadhaar_pattern = Pattern(name="aadhaar_pattern", regex=r"\b\d{12}\b", score=0.8)
aadhaar_recognizer = PatternRecognizer(supported_entity="IN_AADHAAR", patterns=[aadhaar_pattern])
analyzer.registry.add_recognizer(aadhaar_recognizer)

# Custom operators for faker substitution
def fake_name(_): return fake.name()
def fake_phone(_): return fake.phone_number()
def fake_email(_): return fake.email()
def fake_pan(text): return fpe_encrypt_pan(text)
def fake_aadhaar(text): return fpe_encrypt_aadhaar(text)

# Mapping Presidio entities to our Faker functions
operators = {
    "PERSON": OperatorConfig("custom", {"lambda": fake_name}),
    "PHONE_NUMBER": OperatorConfig("custom", {"lambda": fake_phone}),
    "EMAIL_ADDRESS": OperatorConfig("custom", {"lambda": fake_email}),
    "IN_PAN": OperatorConfig("custom", {"lambda": fake_pan}),
    "IN_AADHAAR": OperatorConfig("custom", {"lambda": fake_aadhaar}),
    "DEFAULT": OperatorConfig("replace", {"new_value": "<REDACTED>"})
}

def mask_text(text: str) -> str:
    if pd.isna(text) or not isinstance(text, str):
        return text
        
    results = analyzer.analyze(text=text, entities=["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS", "IN_PAN", "IN_AADHAAR"], language='en')
    
    if not results:
        return text
        
    anonymized_result = anonymizer.anonymize(
        text=text,
        analyzer_results=results,
        operators=operators
    )
    return anonymized_result.text

def add_laplace_noise(series: pd.Series, epsilon: float = 1.0, sensitivity: float = 1000.0) -> pd.Series:
    """Adds Laplace noise for Differential Privacy."""
    scale = sensitivity / epsilon
    noise = np.random.laplace(0, scale, len(series))
    noisy_series = series + noise
    return noisy_series.round(2).clip(lower=0) # ensure positive amounts

def generalize_age(age: int) -> str:
    if pd.isna(age): return age
    age = int(age)
    if age < 25: return "18-25"
    elif age < 35: return "26-35"
    elif age < 50: return "36-50"
    elif age < 65: return "51-65"
    else: return "65+"

def generalize_pincode(pincode: str) -> str:
    if pd.isna(pincode): return pincode
    return str(pincode)[:3] + "XXX"

def process_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    masked_df = df.copy()
    
    logger.info("Starting masking process...")
    
    # 1. Direct PII Masking (FPE for PAN/Aadhaar)
    if 'PAN_Number' in masked_df.columns:
        masked_df['PAN_Number'] = masked_df['PAN_Number'].apply(fpe_encrypt_pan)
    if 'Aadhaar_Number' in masked_df.columns:
        masked_df['Aadhaar_Number'] = masked_df['Aadhaar_Number'].apply(fpe_encrypt_aadhaar)
    
    if 'Account_Number' in masked_df.columns:
        # FPE or Hash
        masked_df['Account_Number'] = masked_df['Account_Number'].apply(lambda x: hash(str(x)) % 10**10 if pd.notna(x) else x)

    # 2. Text Masking for PII embedded in comments/names/emails
    text_columns = ['Name', 'Phone_Number', 'Email', 'Comments']
    for col in text_columns:
        if col in masked_df.columns:
            logger.info(f"Masking column: {col}")
            masked_df[col] = masked_df[col].apply(mask_text)
            
    # 3. Generalization for Quasi-Identifiers (K-Anonymity)
    if 'Age' in masked_df.columns:
        masked_df['Age'] = masked_df['Age'].apply(generalize_age)
    if 'Pincode' in masked_df.columns:
        masked_df['Pincode'] = masked_df['Pincode'].apply(generalize_pincode)

    # 4. Differential Privacy for Financial Amounts
    if 'Amount' in masked_df.columns:
        logger.info("Applying Laplace noise to Amount to ensure DP")
        masked_df['Amount'] = add_laplace_noise(masked_df['Amount'], epsilon=1.0, sensitivity=1000.0)

    logger.info("Masking complete.")
    return masked_df

if __name__ == "__main__":
    df = pd.read_csv("raw_fintech_data.csv")
    masked_df = process_dataframe(df)
    masked_df.to_csv("masked_fintech_data.csv", index=False)
    print("Saved masked_fintech_data.csv")
