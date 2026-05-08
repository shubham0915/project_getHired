"""
Masker — Irreversible Faker-Based PII Substitution Engine

This module replaces detected PII with realistic, irreversible synthetic values
using Faker (en_IN locale). Key design principles:

1. IRREVERSIBLE: No encryption keys, no mapping tables that could be leaked.
   Once masked, the original value is gone. (Mentor requirement)
   
2. DETERMINISTIC WITHIN SESSION: Same input PII → same output value within
   a single processing run. This preserves referential integrity:
   "Raj Kumar" in row 5 and row 50 both become "Amit Sharma" consistently.
   (Research File 5: F1 Mask Redis Vault pattern)

3. FORMAT PRESERVING: PAN → PAN-like string, Phone → Phone-like string.
   The masked data looks real, hiding "in plain sight".
   (Research: "Hide in Plain Sight" philosophy)

4. CONFIGURABLE: Faker methods are mapped to PII types via pii_config.yaml.
"""

import os
import random
import string
import hashlib
import hmac
import pandas as pd
from typing import Dict, Optional, Any
from faker import Faker
import logging

logger = logging.getLogger(__name__)

# Initialize Faker with Indian locale for realistic data
fake = Faker('en_IN')
Faker.seed(42)  # Reproducible for testing; remove in production


class PIIMasker:
    """
    Generates irreversible, format-preserving synthetic replacements for PII.
    
    Uses a deterministic mapping cache: within a single session (process_dataframe call),
    the same original value always maps to the same masked value. This preserves
    referential integrity across the dataset.
    """

    def __init__(self, salt: Optional[str] = None):
        # Session-level deterministic cache: original_value → masked_value
        self._cache: Dict[str, str] = {}
        # Pull salt from environment variable (Enterprise standard) to avoid hardcoding
        self.salt = salt or os.getenv("MASKING_SALT", "BL0STEM_HACK_2026")

    def _get_seed(self, text: str) -> int:
        """Generate a deterministic seed from text using a salted SHA-256 hash."""
        import hashlib
        # Salted hash ensures it's irreversible even if the mapping logic is known
        combined = f"{self.salt}:{text.lower()}"
        hash_hex = hashlib.sha256(combined.encode()).hexdigest()
        # Use first 8 characters for a stable 32-bit integer seed
        return int(hash_hex[:8], 16)

    def reset_cache(self):
        """Reset the deterministic mapping. Call between independent datasets."""
        self._cache.clear()

    @property
    def generated_values(self) -> set:
        """Return the set of all generated masked values (for validator whitelist)."""
        return set(self._cache.values())

    def mask(self, original_value: Any, faker_method: str = "redact") -> str:
        """Mask a single value using the specified Faker method with caching."""
        if pd.isna(original_value) or not str(original_value).strip():
            return original_value

        original_value = str(original_value).strip()
        
        # Lowercase the key to handle case-insensitivity ('Rajesh' vs 'rajesh')
        cache_key = f"{faker_method}::{original_value.lower()}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Generate replacement based on method
        masked = self._generate(original_value, faker_method)
        self._cache[cache_key] = masked
        
        # If it's a person's name, cache the partial names to maintain referential integrity
        # e.g., if 'Rajesh Sharma' -> 'Sanjay Tailor', then later 'Rajesh' -> 'Sanjay'
        if faker_method in ("person", "name"):
            parts = original_value.lower().split()
            masked_parts = masked.split()
            
            if len(parts) >= 1 and len(masked_parts) >= 1:
                first_name_key = f"{faker_method}::{parts[0]}"
                if first_name_key not in self._cache:
                    self._cache[first_name_key] = masked_parts[0]
                    
            if len(parts) >= 2 and len(masked_parts) >= 2:
                last_name_key = f"{faker_method}::{parts[-1]}"
                if last_name_key not in self._cache:
                    self._cache[last_name_key] = masked_parts[-1]
                    
        return masked

    def _generate(self, original: str, method: str) -> str:
        """Route to the appropriate faker generator with deterministic seeding."""
        # Seed both random and faker to ensure cross-session consistency
        # (Gap 1: Salted Hash Alternative for Referential Integrity)
        seed = self._get_seed(original)
        random.seed(seed)
        fake.seed_instance(seed)

        generators = {
            "hash": self._hash_token,
            "pan": self._fake_pan,
            "aadhaar": self._fake_aadhaar,
            "ifsc": self._fake_ifsc,
            "credit_card": self._fake_credit_card,
            "upi_id": self._fake_upi_id,
            "phone_number": self._fake_phone,
            "email": self._fake_email,
            "pincode": self._fake_pincode,
            "date_of_birth": self._fake_dob,
            "date_of_birth_iso": self._fake_dob_iso,
            "passport": self._fake_passport,
            "vehicle_registration": self._fake_vehicle,
            "bank_account": self._fake_bank_account,
            "transaction_ref": self._fake_transaction_ref,
            "gstin": self._fake_gstin,
            # GLiNER detected types
            "person": self._fake_name,
            "name": self._fake_name,
            "address": self._fake_address,
            "organization": self._fake_organization,
            "obfuscate": self._obfuscate_format,
            "redact": self._redact,
        }

        generator = generators.get(method, self._redact)
        return generator(original)

    # -----------------------------------------------------------------------
    # Indian Fintech Faker Generators
    # -----------------------------------------------------------------------

    def _fake_pan(self, original: str) -> str:
        """Generate a realistic Indian PAN: ABCDE1234F"""
        letters_first = ''.join(random.choices(string.ascii_uppercase, k=5))
        digits = ''.join(random.choices(string.digits, k=4))
        letter_last = random.choice(string.ascii_uppercase)
        return f"{letters_first}{digits}{letter_last}"

    def _fake_aadhaar(self, original: str) -> str:
        """Generate a realistic, mathematically valid Aadhaar (Verhoeff checksum)."""
        # Generate first 11 digits (starts with 2-9)
        first = str(random.randint(2, 9))
        eleven_digits = f"{first}{''.join(random.choices(string.digits, k=10))}"
        
        # Verhoeff math tables for generating checksum
        d_table = [
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 2, 3, 4, 0, 6, 7, 8, 9, 5], [2, 3, 4, 0, 1, 7, 8, 9, 5, 6],
            [3, 4, 0, 1, 2, 8, 9, 5, 6, 7], [4, 0, 1, 2, 3, 9, 5, 6, 7, 8], [5, 9, 8, 7, 6, 0, 4, 3, 2, 1],
            [6, 5, 9, 8, 7, 1, 0, 4, 3, 2], [7, 6, 5, 9, 8, 2, 1, 0, 4, 3], [8, 7, 6, 5, 9, 3, 2, 1, 0, 4],
            [9, 8, 7, 6, 5, 4, 3, 2, 1, 0]
        ]
        p_table = [
            [0, 1, 2, 3, 4, 5, 6, 7, 8, 9], [1, 5, 7, 6, 2, 8, 3, 0, 9, 4], [5, 8, 0, 3, 7, 9, 6, 1, 4, 2],
            [8, 9, 1, 6, 0, 4, 3, 5, 2, 7], [9, 4, 5, 3, 1, 2, 6, 8, 7, 0], [4, 2, 8, 6, 5, 7, 3, 9, 0, 1],
            [2, 7, 9, 3, 8, 0, 6, 4, 1, 5], [7, 0, 4, 6, 9, 1, 3, 2, 5, 8]
        ]
        inv_table = [0, 4, 3, 2, 1, 5, 6, 7, 8, 9]

        c = 0
        p = list(map(int, eleven_digits))
        p.reverse()
        for i, val in enumerate(p):
            c = d_table[c][p_table[(i + 1) % 8][val]]
        
        check_digit = inv_table[c]
        return f"{eleven_digits}{check_digit}"

    def _fake_ifsc(self, original: str) -> str:
        """Generate a realistic IFSC: ABCD0123456"""
        bank = ''.join(random.choices(string.ascii_uppercase, k=4))
        branch = ''.join(random.choices(string.digits + string.ascii_uppercase, k=6))
        return f"{bank}0{branch}"

    def _fake_credit_card(self, original: str) -> str:
        """Generate a realistic credit card number."""
        return fake.credit_card_number(card_type="visa")

    def _fake_upi_id(self, original: str) -> str:
        """Generate a realistic UPI ID."""
        username = fake.user_name()
        banks = ["ybl", "paytm", "okhdfcbank", "okicici", "apl"]
        return f"{username}@{random.choice(banks)}"

    def _fake_phone(self, original: str) -> str:
        """Generate a realistic Indian phone number."""
        # Preserve format: if original has +91, keep it
        prefix = "+91 " if original.startswith("+91") else ""
        number = f"{random.randint(6, 9)}{''.join(random.choices(string.digits, k=9))}"
        return f"{prefix}{number}"

    def _fake_email(self, original: str) -> str:
        """Generate a realistic email."""
        return fake.email()

    def _fake_pincode(self, original: str) -> str:
        """Generate a realistic Indian pincode."""
        return str(random.randint(110001, 855117))

    def _fake_dob(self, original: str) -> str:
        """Generate a realistic DOB in same format as original."""
        dob = fake.date_of_birth(minimum_age=18, maximum_age=80)
        # Detect format from original
        if "/" in original:
            return dob.strftime("%d/%m/%Y")
        # Check if it's ISO format (YYYY-MM-DD) — first 4 chars are year
        if len(original) >= 10 and original[:4].isdigit() and original[4] == '-':
            return dob.strftime("%Y-%m-%d")
        return dob.strftime("%d-%m-%Y")

    def _fake_dob_iso(self, original: str) -> str:
        """Generate a realistic DOB in ISO 8601 format (YYYY-MM-DD)."""
        dob = fake.date_of_birth(minimum_age=18, maximum_age=80)
        return dob.strftime("%Y-%m-%d")

    def _fake_passport(self, original: str) -> str:
        """Generate a realistic Indian passport number."""
        letter = random.choice(string.ascii_uppercase)
        digit = str(random.randint(1, 9))
        rest = ''.join(random.choices(string.digits, k=6))
        return f"{letter}{digit}{rest}"

    def _fake_vehicle(self, original: str) -> str:
        """Generate a realistic Indian vehicle registration."""
        state = ''.join(random.choices(string.ascii_uppercase, k=2))
        dist = str(random.randint(1, 99)).zfill(2)
        series = ''.join(random.choices(string.ascii_uppercase, k=2))
        num = str(random.randint(1, 9999)).zfill(4)
        return f"{state}-{dist}-{series}-{num}"

    def _fake_bank_account(self, original: str) -> str:
        """Generate a realistic bank account number (same length as original)."""
        length = len(original) if len(original) >= 9 else 12
        return ''.join(random.choices(string.digits, k=length))

    def _fake_transaction_ref(self, original: str) -> str:
        """Generate a synthetic transaction reference ID preserving prefix format.
        
        ORD1248848721 → ORD + 10 random digits
        FD38802228    → FD + 8 random digits
        """
        import re as _re
        m = _re.match(r'^([A-Z]+)(\d+)$', original)
        if m:
            prefix = m.group(1)
            digit_len = len(m.group(2))
            return f"{prefix}{''.join(random.choices(string.digits, k=digit_len))}"
        # Fallback: obfuscate entire string
        return self._obfuscate_format(original)

    def _fake_gstin(self, original: str) -> str:
        """Generate a realistic, mathematically valid GSTIN (Modulo 36 checksum)."""
        # State code (01-35)
        state_code = str(random.randint(1, 35)).zfill(2)
        # PAN (10 chars)
        pan = self._fake_pan("")
        # Entity code (1-9 or A-Z)
        entity = random.choice("123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        # Default character is Z
        gstin_14 = f"{state_code}{pan}{entity}Z"
        
        # Calculate 15th checksum digit
        alphanumeric = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        char_to_val = {char: i for i, char in enumerate(alphanumeric)}
        factor = 1
        total = 0
        for char in gstin_14:
            val = char_to_val[char]
            digit = val * factor
            digit = (digit // 36) + (digit % 36)
            total += digit
            factor = 2 if factor == 1 else 1
            
        remainder = total % 36
        checksum_val = (36 - remainder) % 36
        
        return f"{gstin_14}{alphanumeric[checksum_val]}"

    # -----------------------------------------------------------------------
    # Gender-Aware Indian Name Masking (Hybrid Approach)
    # -----------------------------------------------------------------------
    # First names: Curated Indian lists → guarantees Indian + correct gender
    # Surnames:    Faker en_IN last_name() → 517+ unique Indian surnames
    #
    # Combo pool: 50 first × 517 surnames = ~25,850 per gender (51,700 total)
    # This scales to production datasets while guaranteeing every name is
    # authentically Indian. Research File 1 suggested DeBERTa (400MB) for
    # gender — our suffix heuristic achieves the same with zero overhead.

    # Curated Indian male first names (50)
    _INDIAN_MALE_FIRST = [
        'Aarav', 'Arjun', 'Vihaan', 'Aditya', 'Vivaan', 'Reyansh', 'Ayaan',
        'Krishna', 'Sai', 'Arnav', 'Dhruv', 'Kabir', 'Ritvik', 'Anirudh',
        'Harsh', 'Pranav', 'Ishaan', 'Rohan', 'Karthik', 'Manish',
        'Suresh', 'Ramesh', 'Mahesh', 'Ganesh', 'Rajesh', 'Vikram', 'Amit',
        'Sumit', 'Rohit', 'Mohit', 'Nikhil', 'Rahul', 'Deepak', 'Ankur',
        'Gaurav', 'Varun', 'Tarun', 'Kunal', 'Vishal', 'Akash',
        'Sanjay', 'Vijay', 'Ajay', 'Naveen', 'Pavan', 'Chetan', 'Sachin',
        'Yogesh', 'Dinesh', 'Rakesh',
    ]

    # Curated Indian female first names (50)
    _INDIAN_FEMALE_FIRST = [
        'Aanya', 'Ananya', 'Aadhya', 'Diya', 'Myra', 'Isha', 'Kavya',
        'Saanvi', 'Anika', 'Riya', 'Priya', 'Shreya', 'Tanvi', 'Aditi',
        'Pooja', 'Neha', 'Meera', 'Nisha', 'Anjali', 'Sunita',
        'Rekha', 'Deepika', 'Pallavi', 'Swati', 'Shalini', 'Komal', 'Jyoti',
        'Manisha', 'Rashmi', 'Sneha', 'Divya', 'Sakshi', 'Nikita', 'Kriti',
        'Lavanya', 'Simran', 'Bhavna', 'Geeta', 'Radha', 'Archana',
        'Shweta', 'Garima', 'Aparna', 'Ritika', 'Sonali', 'Preeti', 'Kanika',
        'Namrata', 'Anisha', 'Tanya',
    ]

    # Indian female first name suffix patterns (for gender inference)
    _FEMALE_SUFFIXES = (
        'ika', 'ita', 'iya', 'isha', 'ashi', 'ushi', 'athi',
        'tha', 'dha', 'sha', 'shi', 'chi',
        'ya', 'ka', 'ni', 'ti', 'vi', 'ri', 'hi', 'li',
        'na', 'ta', 'ha', 'da',
        'a', 'i',
    )

    # Indian male first name suffix patterns
    _MALE_SUFFIXES = (
        'esh', 'ash', 'ish', 'ush',
        'deep', 'nath', 'kumar', 'raj', 'pal', 'dev', 'ram',
        'an', 'ar', 'av', 'aj', 'al', 'in', 'ur', 'en',
        'sh', 'ab', 'ek', 'il',
    )

    # Explicit overrides for Western/ambiguous names common in en_IN Faker data
    _KNOWN_MALE = {
        'luke', 'george', 'max', 'simon', 'peter', 'robert', 'samuel',
        'isaiah', 'yash', 'amit', 'raj', 'vikram', 'umang', 'faraj',
        'arjun', 'rohan', 'aarav', 'vihaan', 'aditya', 'sai',
        'john', 'james', 'david', 'michael', 'daniel', 'mark', 'paul',
    }
    _KNOWN_FEMALE = {
        'priya', 'neha', 'ananya', 'diya', 'isha', 'riya', 'sara',
        'aisha', 'zara', 'mira', 'nisha', 'pooja', 'kavya', 'aditi',
        'mary', 'sarah', 'emily', 'emma', 'anna', 'jane', 'alice',
    }

    @staticmethod
    def _infer_gender(full_name: str) -> str:
        """
        Infer gender from an Indian name using suffix heuristics.
        Returns: 'M' (male), 'F' (female), or 'U' (unknown)
        """
        first_name = full_name.strip().split()[0].lower()

        if first_name in PIIMasker._KNOWN_MALE:
            return 'M'
        if first_name in PIIMasker._KNOWN_FEMALE:
            return 'F'

        for suffix in PIIMasker._FEMALE_SUFFIXES:
            if first_name.endswith(suffix) and len(first_name) > len(suffix) + 1:
                return 'F'

        for suffix in PIIMasker._MALE_SUFFIXES:
            if first_name.endswith(suffix) and len(first_name) > len(suffix) + 1:
                return 'M'

        return 'U'

    def _fake_name(self, original: str) -> str:
        """
        Generate a gender-preserving, authentically Indian name.
        
        WORD-COUNT AWARE:
        - 1 word input → single-word output (first name OR surname)
        - 2+ word input → "First Last" output
        
        Detects whether a single word is a first name or surname by
        checking against the curated lists. This ensures:
        - "Gaurav" → "Rakesh"  (not "Rakesh Patel")
        - "Verma"  → "Sharma"  (not "Priya Sharma")
        - "Gaurav Verma" → "Rakesh Sharma"
        """
        word_count = len(original.strip().split())
        gender = self._infer_gender(original)

        if word_count <= 1:
            # Single word — is it a first name or a surname?
            original_lower = original.strip().lower()

            # Check if it's a known surname
            from core.pipeline import MaskingPipeline
            is_surname = original_lower in {
                s.lower() if isinstance(s, str) else s
                for s in MaskingPipeline._COMMON_INDIAN_SURNAMES
            }
            is_first_name = original_lower in {
                n.lower() for n in (self._INDIAN_MALE_FIRST + self._INDIAN_FEMALE_FIRST)
            }

            if is_surname and not is_first_name:
                # It's a surname → return surname only
                return fake.last_name()
            else:
                # It's a first name (or unknown) → return first name only
                if gender == 'F':
                    return random.choice(self._INDIAN_FEMALE_FIRST)
                elif gender == 'M':
                    return random.choice(self._INDIAN_MALE_FIRST)
                else:
                    return random.choice(self._INDIAN_MALE_FIRST + self._INDIAN_FEMALE_FIRST)
        else:
            # Multi-word → full name "First Last"
            if gender == 'F':
                first = random.choice(self._INDIAN_FEMALE_FIRST)
            elif gender == 'M':
                first = random.choice(self._INDIAN_MALE_FIRST)
            else:
                first = random.choice(self._INDIAN_MALE_FIRST + self._INDIAN_FEMALE_FIRST)
            surname = fake.last_name()
            return f"{first} {surname}"

    def _fake_address(self, original: str) -> str:
        """Generate a realistic Indian address."""
        return fake.address().replace("\n", ", ")

    def _fake_organization(self, original: str) -> str:
        """Generate a realistic company name."""
        return fake.company()

    def _obfuscate_format(self, original: str) -> str:
        """
        Generic format-preserving obfuscation.
        Replaces uppercase letters with random uppercase, lowercase with random lowercase,
        and digits with random digits. Leaves special characters intact.
        Perfect for identifiers like GSTIN, CIN, UDYAM, etc.
        """
        result = []
        for char in original:
            if char.isdigit():
                result.append(random.choice(string.digits))
            elif char.isupper():
                result.append(random.choice(string.ascii_uppercase))
            elif char.islower():
                result.append(random.choice(string.ascii_lowercase))
            else:
                result.append(char)
        return ''.join(result)

    def _hash_token(self, original: str) -> str:
        """Deterministic HMAC-SHA256 token for high-cardinality IDs."""
        digest = hmac.new(self.salt.encode(), original.encode(), hashlib.sha256).hexdigest()
        return f"ID_{digest[:12].upper()}"

    def _redact(self, original: str) -> str:
        """Fallback: replace with a generic redaction marker."""
        return "[REDACTED]"
