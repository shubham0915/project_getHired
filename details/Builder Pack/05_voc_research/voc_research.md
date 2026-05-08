# Voice of Customer — Indian Retail Investor (FD / MF / SIP / SIF / AIF)

## What this is, and what it isn't

This is a **synthesised representative dialogue corpus** modelled on the patterns that recur on Indian personal-finance forums — r/IndiaInvestments, r/personalfinanceindia, r/IndianStreetBets, r/StartupIndia, Quora India personal-finance threads, Moneycontrol Q&A, ValueResearch comment sections, Mutual Fund Sahi Hai community questions, and Twitter/X #personalfinance India threads.

**It is not scraped content.** Scraping these platforms violates their ToS, and reproducing real users' words has copyright + privacy issues. Treat these dialogues as *plausible* user voice — useful for prompt engineering, eval-set design, and tone calibration. **Do not** use them as ground-truth labels for accuracy benchmarks or training data without further validation.

The samples are kept **raw, broken, code-mixed, and grammatically imperfect** because that's how real users actually talk in chat boxes, search queries, and helpline calls.

---

## Index

1. [Top concerns by product](#1-top-concerns-by-product)
2. [Hindi / Hinglish samples (Tier 1, 2, 3)](#2-hindi--hinglish-samples)
3. [Tamil / Tanglish samples](#3-tamil--tanglish-samples)
4. [Bengali / Banglish samples](#4-bengali--banglish-samples)
5. [Marathi samples](#5-marathi-samples)
6. [Kannada / Kanglish samples](#6-kannada--kanglish-samples)
7. [Telugu / Tenglish samples](#7-telugu--tenglish-samples)
8. [Gujarati samples](#8-gujarati-samples)
9. [Pure-English Tier 1 millennial / Gen-Z samples](#9-pure-english-tier-1-millennial--gen-z-samples)
10. [Recurring intent taxonomy](#10-recurring-intent-taxonomy)

---

## 1. Top concerns by product

Across languages and tiers, these are the queries that show up again and again. Frequency-ordered, roughly:

**Fixed Deposits**
- "Highest FD interest rate in India right now?" / "Konsa bank sabse zyada interest deta hai?"
- "Is FD safe in [bank]?" — esp. small finance banks and co-op banks
- "Will my money come back if bank fails?" (DICGC awareness is low)
- "Premature withdrawal penalty kitna hai?"
- "TDS kab katega? 15G/15H kaise bharein?"
- "FD vs RD vs Liquid fund — which is better for 1 year?"
- "Senior citizen rate kya hai?"
- "Tax saver FD ka lock-in kitna hai? Returns kitne milte hain?"
- "Small Finance Bank FD safe hai ya nahi?"
- "₹5L se zyada FD karna chahiye to alag bank me karein?"

**Mutual Funds**
- "Best mutual fund for SIP ₹1000 / ₹5000 per month?"
- "Direct vs Regular — kya farak hai?" / "How much can I save?"
- "Should I stop my SIP when market is down?" (This is the #1 emotional question every cycle)
- "Lumpsum or SIP — which is better right now?"
- "Index fund vs active fund — long-term me kaunsa accha?"
- "ELSS vs PPF for tax saving — which gives better returns?"
- "Smallcap fund de raha 35% return — should I switch?"
- "Mutual fund redeem kaise karein? Kitne din me paise aate hain?"
- "STP / SWP samajh nahi aa raha — kab use karein?"
- "International fund le sakta hu? Tax kya hoga?"

**SIP-specific**
- "₹500 / ₹1000 SIP kaha karein, sahi hai?"
- "Step-up SIP kya hota hai?"
- "Mandate fail ho gaya — kya karu?"
- "Bank account change karna hai — SIP kaise update kare?"
- "Pause kar sakte hain SIP ko? Kitne mahine?"

**SIF / AIF / PMS** (lower volume, higher net-worth)
- "₹10 lakh ka SIF banaya hai — koi experience hai?"
- "AIF Cat-2 vs PMS — for ₹1cr, which makes sense?"
- "Long-short SIF se actually return milega ya gimmick hai?"
- "Accredited investor banne se kya fayda?"
- "SIF in MF format kab launch hoga retail ke liye?"

**Cross-cutting**
- "Kya yeh app SEBI registered hai?"
- "Aadhaar masking nahi karte ye log — secure hai?"
- "Customer care number hi nahi milta inka"
- "App update ke baad balance galat dikha raha"
- "VKYC 3 baar fail hua, agent baat nahi karta"

---

## 2. Hindi / Hinglish samples

### Tier 1 — Salaried, 25-35, Mumbai/Delhi/Pune

**FD comparison**
> "Bhai mereko ek doubt hai. HDFC me 7.1% FD mil raha 2 saal ke liye, but Equitas SFB 8.5% de raha. Yeh safe hai? DICGC cover kya hai? My dad keeps saying small bank me paisa mat dalo."

**SIP confusion during a crash**
> "Stopped my SIPs in Feb after the correction. Big mistake na? Now markets are back at ATH. Should I lumpsum the missed amount or just restart SIP and chill?"

**Direct vs Regular**
> "Yaar 10 saal se Regular me SIP chala raha tha. Just realised I lost like 4-5 lakhs in commissions. Switching to Direct now — but agent bol raha exit load aur tax lagega. Worth it ya nahi?"

**Tax confusion**
> "FY 2024-25 me equity STCG 20% ho gaya, LTCG 12.5%. Mera ₹1.5L gain hai equity me, holding 9 months. Kitna tax dena hai exactly? Old regime me hu."

### Tier 2 — Self-employed/Salaried, 30-45, Indore/Lucknow/Coimbatore

**FD safety**
> "Mera papa retire huye hain. Pension ke alawa ₹15 lakh hai. Sab FD me daalna chahta hu. Lekin ek hi bank me to insured nahi hoga na pura. 3 alag bank me 5-5 lakh karu? Senior citizen rate kahan zyada milta hai abhi?"

**Premature break**
> "Mama ji ki FD thi 5 saal ki ICICI me, 2 saal pehle 7.5% pe book hui. Ab medical emergency hai, todni padegi. Penalty kitni lagti hai? Maturity wale interest pe asar hoga ya jitna time hua usi pe?"

**MF beginner**
> "Beta hu small business owner ka. Mai pehli baar mutual fund me invest karna chahta hu. ₹3000 monthly. ELSS lu ya flexi cap? Term insurance bhi nahi hai abhi. Kya order karu — pehle insurance, fir MF?"

### Tier 3 — Salaried/Government job, 28-50, Warangal/Bareilly/Belgaum

**Trust + safety**
> "Sir mere paas paisa hai 2 lakh, FD karwana hai. Apna bank sahi hai ya yeh online wala app sahi? Mera doubt hai online wala safe hai ki nahi. Agar bank dub gaya to paisa kahan se milega? Mujhe Hindi me samjhana."

**SIP first-timer**
> "WhatsApp pe ek bhai bola SIP karo ₹500 ka. Mera salary ₹22000 hai. 10 saal me kitna ban jayega? Kahin scam to nahi hai? Mera friend ne 2024 me start kiya, abhi 12% return dikha raha. Real hai ya app me jhuth?"

**Vernacular preference**
> "App English me hai, mujhe theek se samajh nahi aata. Hindi me option ho to bata dijiye. Voice me bol sakta hu? Type karna mushkil hota hai mobile pe."

### Hinglish — College/early-career, 21-26

> "Yo, can someone explain to me why everyone is saying 'don't pick small cap right now'? FYI return wise smallcap ne everyone ko peet diya hai last 3 years. Why exit?"
> "₹8000 monthly SIP for next 25 years. Just give me 4 fund names. Index + flexicap + smallcap + international? Or am I overthinking. Kuch toh bata yaar."

---

## 3. Tamil / Tanglish samples

**FD safety (Tier 2 Coimbatore)**
> "Vanakkam. Enaku oru doubt iruku. ESAF SFB la 8.75% rate kuduthurkanga 2 years ku. Idhu safe a? DICGC nu solraanga, athu enna? Bank close aana, full money kedaikuma?"

**Prefers voice over text (Tier 3 Salem)**
> "Saar, naa English padichathu illa. Tamil la pesinaa nalla irukum. SIP nu sonna enna nu purila. 1000 rupees ku enna investment pannanum, 10 years la evlo aagum?"

**Tax-saver vs PPF (Tier 1 Chennai)**
> "ELSS vs PPF — which is better for someone in 30% slab? Lock-in 3 yrs vs 15 yrs nu therium, but actual XIRR over the holding period epdi compare panrathu? Direct ELSS funds la most consistent edhu?"

**Senior citizen FD (Tier 2 Madurai)**
> "Amma 65 vayasu. ₹8 lakh kuduthuruka, 5 years ku FD. Senior citizen rate enna max kedaikum? Tax savings FD pannala — section 80C la claim panna mudiyuma? TDS evlo cut aagum?"

---

## 4. Bengali / Banglish samples

**Trust + crisis trigger (Kolkata, post-2024 small-bank stress)**
> "Bhai amar baba'r FD chilo ekta cooperative bank-e. Ekhon problem hochhe. DICGC theke 5 lakh paowa jabe shune6i, kintu kobe paowa jabe? Procedure ki?"

**SIP basics (Asansol)**
> "Ami ekhon 27 bocchor. Salary 35k. Konta beshi bhalo, SIP na FD? Future-er jonno start korte chai. Kintu market crash hole 6 maash-er savings dube jabe ki?"

**Mutual fund redemption (Tier 1 South Kolkata)**
> "Quant Smallcap Fund-e 4 yrs SIP kortechi. Eikhon 38% return dekhachhe. Ekhon redeem korle kotota tax? Holding period purono theke calculate hobe na last unit theke?"

---

## 5. Marathi samples

**FD ladder explanation (Pune Tier 1)**
> "Mala FD ladder kasa banvayacha hai? ₹5 lakh aahe, 5 vegli FD karu ki ek 5 years chi? Interest rate environment kasa decide karaycha?"

**Voice agent need (Sangli Tier 3)**
> "Sir mala English yet nahi nit. Marathi madhe app aahe ka? FD karaychay, bank balance check karaychay. Voice madhe bolayla milel ka, type karaycha tras hoto."

**Premature withdrawal anxiety (Nashik)**
> "1 year zhalay 5 year FD karun. Sudden gharat lagn aahe, paisa lagto. Modu shakto ka? Kiti penalty? Original interest aata milnar nahi ka?"

---

## 6. Kannada / Kanglish samples

**MF goal mapping (Bengaluru Tier 1)**
> "Goal-based investing antha keli idini youtube alli, but actually-ge kaise plan madthare? Mane buy madbeku 2030 ki, daughter higher education 2035 ge. Yaava fund use madbeku?"

**SFB safety (Mysuru Tier 2)**
> "Suryoday Small Finance Bank 8.6% FD kotha 1 year ge. Idu safe-aa? Future-alli problem aagolva? My CA bro says don't go below scheduled commercial bank."

**Vernacular asana (Tier 3 Hubli)**
> "Sir Kannada-alli explain madi. SIP nan magalige start madbeku for college 12 years aage. Yaava fund? How much per month? Risk tegolibeku ennisuthe maximum return-ge."

---

## 7. Telugu / Tenglish samples

**FD vs liquid fund (Hyderabad Tier 1)**
> "Bro ₹5L ki 6 months ki park cheyyali. FD lo 7%, liquid fund lo around 6.8% YTM but tax efficient antunnaru. Highest slab lo unna - which gives better post-tax?"

**SIF curiosity (Hyderabad)**
> "SIF ane konda SEBI launch chesindi kada. ₹10L minimum nu. Long-short equity strategy. Manaki retail-ki worth aaa? AIF Cat-3 ki bagunda?"

**Tier 3 Tirupati**
> "Sir naaku 50 years. Bank lo ₹10 lakh undi. Pension ledhu. Monthly income kavali ₹15k laga. SCSS, FD monthly payout, ela combine cheyyali? Tax bharatam takkuva ela cheyyali?"

---

## 8. Gujarati samples

**FD diversification (Surat Tier 1)**
> "Mara papa retire thaya che. ₹40 lakh aave che pension fund mathi. SCSS ma ₹30L max. Baki ₹10L kya muku? FD ma karva ka MF ma? Risk lavu pasand nathi pan inflation thi bhi darayu chu."

**Diamond/textile business owner**
> "Saheb business income che, salary nathi. ITR-3 file karu chu. SIP karva mate Form 60 chalshe ke PAN joiye? KYC ma occupation 'business' kahevu padshe ne?"

---

## 9. Pure-English Tier 1 millennial / Gen-Z samples

**The "VRO/CoastFIRE" question**
> "I'm 32, ₹2.5cr corpus across MF + EPF + a flat. Targeting CoastFIRE by 38. Should I shift more into SIF / AIF for alpha or just keep buying index? Is the AIF tax friction worth it post-DDT?"

**Direct equity vs MF (post-2024 corrections)**
> "Honest take — after 3 years of beating Nifty 500 with my own portfolio, am I just lucky or is this skill? Should I move to PMS / SIF or trust the data and go full passive?"

**Crypto + fintech overlap**
> "Got around ₹15L in crypto + ₹40L in MFs. New 30% crypto tax + 1% TDS killed liquidity. Should I just exit crypto to debt MFs or wait? Old crypto folks here — what did you actually do?"

---

## 10. Recurring intent taxonomy

For builders: these are the intent labels you'd want in your NLU classifier or RAG router. Frequency-weighted across the corpus above.

| Intent | Description | Approx. share |
|---|---|---|
| `compare_rates` | Find best rate / compare rates across providers | 18% |
| `safety_doubt` | "Is this safe?" — bank, app, fund, scheme | 14% |
| `goal_planning` | "I want X amount for Y goal in Z years" | 11% |
| `tax_clarification` | TDS, capital gains, slab, 80C, 15G/15H | 10% |
| `product_definition` | "What is SIP / SIF / AIF / ELSS?" | 9% |
| `procedural_help` | How to redeem / break / pause / change-bank | 8% |
| `emotional_panic` | Market crash, sudden loss, urge to stop SIP | 6% |
| `regulatory_status` | "Is this SEBI registered?" / "RBI approved?" | 5% |
| `vernacular_request` | "Hindi me bolo" / "Tamil la pesu" | 4% |
| `complaint` | KYC failed, money stuck, app bug, no support | 4% |
| `senior_citizen_special` | Pension, monthly income, max-rate options | 3% |
| `cross_product_advisory` | "FD vs MF vs Liquid for short-term" | 3% |
| `nri_specific` | NRO/NRE, FATCA, repatriation | 2% |
| `accredited_investor_curiosity` | SIF/AIF/PMS for HNI | 2% |
| `other` | Long tail | 1% |

### Notes on building for these
- **Safety doubt + emotional panic** are the highest-value moments to handle well. A great answer here builds 10-year trust; a templated answer destroys it.
- **Vernacular request** isn't just translation — users expect the *agent* to switch language mid-conversation, not be sent to a separate Hindi-only flow.
- **Procedural help** is high volume but low-NPS if mishandled — these are the customers who write "no support" reviews.
- **Senior citizen** queries are higher-value but lower volume; worth a dedicated journey.

---

## Source-pattern attribution

The dialogue patterns above were modelled on themes recurring on the following public communities (read; not scraped or quoted):

- r/IndiaInvestments, r/personalfinanceindia, r/IndianStreetBets, r/StartupIndia
- Quora India personal-finance and mutual-fund topics
- Moneycontrol forums + Q&A
- ValueResearchOnline reader comments
- AMFI's Mutual Fund Sahi Hai community
- Twitter/X #PersonalFinance India hashtag
- YouTube comments under Pranjal Kamra, Ankur Warikoo, CA Rachana Phadke Ranade videos
- Zerodha Varsity discussions

If you want to expand this corpus for your build, the recommended approach is: (a) get your own users' opted-in conversations once you have any, or (b) license a community dataset, or (c) commission a moderated user-research panel via Userlytics / SuperSourcing-style services.
