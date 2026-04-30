import pandas as pd
from faker import Faker
import random

fake = Faker('en_IN')

def generate_fintech_data(num_records=100):
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
        # Aadhaar is 12 digits
        aadhaar = "".join([str(random.randint(0, 9)) for _ in range(12)])
        # PAN is 5 letters, 4 numbers, 1 letter
        pan = f"{''.join(random.choices('ABCDEFGHIJKLMNOPQRSTUVWXYZ', k=5))}{random.randint(1000, 9999)}{random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')}"
        
        data.append({
            "Transaction_ID": fake.uuid4(),
            "Name": fake.name(),
            "Age": random.randint(18, 85),
            "Pincode": fake.postcode(),
            "Phone_Number": fake.phone_number(),
            "Email": fake.email(),
            "PAN_Number": pan,
            "Aadhaar_Number": aadhaar,
            "Account_Number": fake.bban(),
            "Platform_Source": random.choice(platforms),
            "App_Usage_Score": round(random.uniform(0, 100), 1),
            "Amount": round(random.uniform(100.0, 50000.0), 2),
            "Status": random.choice(statuses),
            "Date": fake.date_this_year(),
            "Comments": f"{random.choice(hindi_comments)} {pan}" if random.random() > 0.7 else random.choice(hindi_comments) # Occasionally leak PAN in comments
        })
    return pd.DataFrame(data)

if __name__ == "__main__":
    df = generate_fintech_data(50)
    df.to_csv("raw_fintech_data.csv", index=False)
    print("Generated raw_fintech_data.csv with 50 records.")
