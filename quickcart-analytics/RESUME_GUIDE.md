# Resume & Interview Guide for the QuickCart Project

Not part of the app. This is for you. Read it fully before you apply anywhere.

## 0. Rules that protect you

1. **Say the data is simulated.** Write "simulated quick-commerce dataset" in the resume or README. Interviewers respect this; they
   do not respect being caught implying real company data.
2. **Only claim what you can explain.** Every bullet below maps to a file in the repo. Open each file and be able to walk through it.
3. **Make it yours.** Many students will find similar projects. Change the cities to ones you know, add one analysis you invent
   (market-basket, CLV forecast, A/B-test simulator), and re-run the pipeline. A project you modified is far easier to defend.

## 1. Resume entry (copy, then fill the two links)

**QuickCart: Quick-Commerce Sales, Retention & Churn Analytics** | Python, SQL, pandas, scikit-learn, Plotly, Streamlit
[Live Demo](https://YOUR-APP-NAME.streamlit.app) · [GitHub](https://github.com/YOUR-USERNAME/quickcart-analytics)

- Designed a SQLite schema and automated data-quality checks for a simulated quick-commerce dataset (9K customers, 45K orders,
  160K line items); wrote 9 analytical SQL queries using CTEs and window functions (LAG, LEAD, NTILE, RANK).
- Built cohort-retention and RFM segmentation analyses: month-1 retention 51% falling to 11% by month 6; "Champions" were 19% of
  customers but 41% of revenue.
- Quantified that deliveries slower than 20 minutes cut 30-day repeat rate from 76% to 58%, and that 25% discounts pushed gross
  margin to -1.6% without improving repeat rate; ranked acquisition channels by LTV:CAC (Referral 3.6x vs Influencer 0.55x).
- Developed a churn model with out-of-time validation (ROC-AUC 0.84); the riskiest 10% of customers churned 98% of the time vs
  58% overall; produced a ranked win-back list of high-value customers.
- Deployed an interactive 7-view Streamlit dashboard with live filters, CSV exports and a read-only SQL lab.

**Short version (one-page resume, 3 bullets):**

- Built an end-to-end analytics project on a simulated quick-commerce dataset (45K orders) using SQL, Python and Streamlit; deployed live.
- Used window-function SQL for cohort retention, RFM segmentation and LTV:CAC; found slow deliveries cut repeat rate 76% to 58% and deep discounts turned margin negative.
- Built a churn model validated on a later time period (ROC-AUC 0.84) and a prioritised win-back list.

**ATS keywords already covered:** SQL, window functions, CTEs, data cleaning, data quality, cohort analysis, retention, RFM, customer
segmentation, LTV, CAC, churn prediction, A/B testing (as next step), KPI dashboard, Python, pandas, scikit-learn, Plotly, Streamlit, EDA.

## 2. LinkedIn and GitHub text

**GitHub description:** End-to-end quick-commerce analytics: SQL cohorts, RFM, LTV:CAC, churn model and a live Streamlit dashboard.
**Topics:** `data-analysis` `sql` `streamlit` `python` `customer-analytics` `churn-prediction` `rfm-analysis` `cohort-analysis`

**LinkedIn Projects / Featured blurb:** I built a quick-commerce analytics dashboard (simulated data) that answers four business
questions: who are the best customers, who is about to churn, which acquisition channel pays back, and whether discounts and slow
deliveries hurt. SQL + Python + Streamlit, live demo in the link. Feedback welcome.

## 3. 60-second walkthrough (say this in interviews)

"I wanted a project that looks like real analyst work, so I simulated a quick-commerce business with realistic rules, loaded it into a
SQL database with quality checks, and answered business questions with SQL. Retention drops sharply after the first month. Orders
delivered in under 20 minutes have a 76% repeat rate versus 58% when slower, so delivery reliability matters more than discounts, which
actually pushed margin negative at 25% off without improving repeat purchase. I segmented customers with RFM, compared channels by
LTV to CAC, and built a churn model validated on a later time window, so it is tested the way it would be used. Finally I deployed
it as a dashboard so a manager can filter and download lists themselves."

## 4. Interview questions you should expect (with answers)

**Why simulated data?** Real company data is private, and public datasets rarely have orders, delivery times, discounts and
acquisition channels together. Simulating let me control the rules, so I could check my analysis recovers them. The tradeoff is the
findings are illustrative; the same SQL runs on real data with the same schema.

**Explain your cohort retention query.** First CTE gets delivered orders by month. Second finds each customer's first-order month
(their cohort). Third computes months since the cohort month for every active month. Then I count distinct customers per cohort and
month index and divide by cohort size. Month 0 is always 100%.

**What is right-censoring and where did you handle it?** An order placed last week has not had 30 days to be followed by a repeat, so
it would wrongly look like churn. In the delivery and discount queries I only include orders at least 30 days before the last date in
the data. Same idea for the 90-day LTV: only customers who signed up 90+ days ago.

**Why out-of-time validation for churn?** A random split lets the model peek at the same period it is tested on. Training on an
earlier snapshot and testing on a later one mimics real use. Features only use data up to the snapshot date, so there is no leakage.

**Why did you restrict the churn population to active customers?** If you score everyone, the model looks great (AUC around 0.95 on
this data) only because it learns that customers who left months ago stay gone. That is trivial and not useful to the business.
Restricting to customers active in the last 90 days gives an honest 0.84 and a real question: who, among the people we can still
save, is about to lapse? (You can reproduce this by removing the `recency_days <= ACTIVE_WINDOW_DAYS` filter in `src/churn_model.py`.)

**Logistic regression beat gradient boosting. Why?** About 2,500 training rows and mostly smooth relationships (recency, gap between
orders). A regularised linear model generalises as well and is easier to explain, so I kept it. I did not tune to chase the number.

**What does 98% in the top decile mean?** Among the 10% of customers the model ranks riskiest, 98% really did not order in the next 60
days, versus 58% overall. Because the base rate is high the maximum lift is about 1.7x, so I report both numbers.

**How reliable is the discount finding?** It is observational. Discounted orders are not random: deal-seeking channels get more of
them. I would run an A/B test, randomising discount level for comparable customers, before changing policy.

**What are the limits of your RFM scoring?** `NTILE` splits tied values arbitrarily (many customers have 1 or 2 orders), and the
segment rules are my judgement. It is a practical segmentation, not a statistical clustering.

**What would you do to scale this?** Move from SQLite to a warehouse (BigQuery or Postgres), schedule the pipeline with Airflow or
cron, version the transformations in dbt, and add monitoring on model AUC and data freshness.

**What data-quality checks did you run?** Orphan foreign keys, orders before signup, non-positive values, invalid status, ratings on
cancelled orders, and reconciling `net_revenue = gross - discount + delivery fee` for every order.

**Which single metric would you give the CEO?** Month-1 retention, because acquisition spend is wasted if customers do not come back,
and it responds to delivery quality and onboarding, which the company controls.

## 5. Make it live and findable (checklist)

- [ ] Public GitHub repo with this folder; README shows your live link and a screenshot (`docs/screenshot.png`).
- [ ] Deployed on Streamlit Community Cloud; open it the day you apply, because idle free apps sleep and take a few seconds to wake.
- [ ] Link the demo and GitHub on your resume as clickable hyperlinks, near your name.
- [ ] Pin the repo on your GitHub profile; add the project to LinkedIn "Featured".
- [ ] Optional: a 60-second screen recording of the dashboard. Hiring managers often watch it instead of opening the app.
- [ ] Optional but strong: rebuild one tab in Power BI or Tableau from `data/raw/*.csv` and mention both tools.
- [ ] Rehearse sections 3 and 4 out loud until you can do them without reading.

## 6. Roles to target

Data Analyst, Business Analyst, Product Analyst, Growth / Marketing Analyst, BI Analyst, Junior Data Scientist at e-commerce,
quick-commerce, fintech and D2C companies. Tailor the first bullet to the company (for example mention "retention" for consumer apps,
"unit economics" for startups).
