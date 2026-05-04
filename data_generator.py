"""
Data Generator — Realistic Indian Fintech Test Data

Generates sample financial data with realistic PII patterns that
match the regex patterns in pii_config.yaml. This ensures the pipeline
can actually detect and mask everything in the test data.
"""

import pandas as pd
from faker import Faker
import random
import string

fake = Faker('en_IN')


def generate_fintech_data(num_records=100):
    """Generate realistic Indian fintech data with proper PII formats."""
    data = []
    statuses = ["SUCCESS", "FAILED", "PENDING"]
    hindi_comments = [
        "FD close karna hai",
        "Mera interest kab aayega?",
        "Nominee add karna hai please",
        "Account balance check karo",
        "Mujhe loan chahiye FD par",
        "Kyc update kaise karein?",
        "Customer care ka number do",
        "Branch transfer request",
        "Sir, mere account se paise kat gaye",
        "Excellent service, thank you"
    ]
    
    platforms = ["Blostem_Direct", "Upstox_Partner", "MobiKwik_Partner", "Zerodha_Partner"]
    
    for _ in range(num_records):
        # Aadhaar: 12 digits, MUST start with 2-9 (matches our regex)
        aadhaar_first = str(random.randint(2, 9))
        aadhaar_rest = ''.join([str(random.randint(0, 9)) for _ in range(11)])
        aadhaar = aadhaar_first + aadhaar_rest

        # PAN: 5 letters + 4 digits + 1 letter (standard Indian PAN)
        pan = (
            ''.join(random.choices(string.ascii_uppercase, k=5))
            + str(random.randint(1000, 9999))
            + random.choice(string.ascii_uppercase)
        )

        # Indian phone: starts with 6-9, exactly 10 digits (matches our regex)
        phone_prefix = str(random.randint(6, 9))
        phone_rest = ''.join(random.choices(string.digits, k=9))
        # Randomly add +91 prefix
        if random.random() > 0.5:
            phone = f"+91 {phone_prefix}{phone_rest}"
        else:
            phone = f"{phone_prefix}{phone_rest}"

        # Generate name using Faker en_IN
        name = fake.name()

        # Generate comment — occasionally embed PII in comments (tests free-text detection)
        if random.random() > 0.7:
            # Embed PAN in comment (30% chance)
            comment = f"{random.choice(hindi_comments)} {pan}"
        elif random.random() > 0.85:
            # Embed name in comment (15% chance) 
            comment = f"{name} ka account check karo"
        else:
            comment = random.choice(hindi_comments)
        
        data.append({
            "Transaction_ID": fake.uuid4(),
            "Name": name,
            "Age": random.randint(18, 85),
            "Pincode": fake.postcode(),
            "Phone_Number": phone,
            "Email": fake.email(),
            "PAN_Number": pan,
            "Aadhaar_Number": aadhaar,
            "Account_Number": fake.bban(),
            "Platform_Source": random.choice(platforms),
            "App_Usage_Score": round(random.uniform(0, 100), 1),
            "Amount": round(random.uniform(100.0, 50000.0), 2),
            "Status": random.choice(statuses),
            "Date": fake.date_this_year(),
            "Comments": comment,
        })
    return pd.DataFrame(data)


if __name__ == "__main__":
    df = generate_fintech_data(50)
    df.to_csv("raw_fintech_data.csv", index=False)
    print(f"Generated raw_fintech_data.csv with {len(df)} records.")
    print(f"Sample PAN: {df['PAN_Number'].iloc[0]}")
    print(f"Sample Aadhaar: {df['Aadhaar_Number'].iloc[0]}")
    print(f"Sample Phone: {df['Phone_Number'].iloc[0]}")
