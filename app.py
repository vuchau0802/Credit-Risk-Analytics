import os, pandas as pd, numpy as np
from flask import Flask, jsonify, render_template

app = Flask(__name__)

DATA_PATH = os.path.join(os.path.dirname(__file__), "cleaned_loan_data (2).csv")
df = pd.read_csv(DATA_PATH, parse_dates=["issue_d"])

GRADE_MAP      = {1:"A", 2:"B", 3:"C", 4:"D", 5:"E"}
INCOME_CAT_MAP = {0.0:"Low (<$40K)", 1.0:"Mid ($40–80K)", 2.0:"High ($80–130K)", 3.0:"Very High (>$130K)"}
STATE_NAMES    = {"MN":"Minnesota","IA":"Iowa","MO":"Missouri","KS":"Kansas",
                  "NE":"Nebraska","SD":"South Dakota","ND":"North Dakota"}

df["grade"]        = df["grade_num"].map(GRADE_MAP)
df["income_label"] = df["income_cat"].map(INCOME_CAT_MAP)

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/api/overview")
def overview():
    return jsonify({
        "total_loans":     int(len(df)),
        "total_amount":    float(df["loan_amnt"].sum()),
        "default_rate":    float(df["default"].mean()),
        "avg_loan":        float(df["loan_amnt"].mean()),
        "avg_int_rate":    float(df["int_rate"].mean()),
        "avg_dti":         float(df["dti"].mean()),
        "avg_revol_util":  float(df["revol_util"].mean()),
        "avg_income":      float(df["annual_inc"].mean()),
        "avg_emp_length":  float(df["emp_length_num"].mean()),
        "avg_installment": float(df["installment"].mean()),
        "states":          int(df["addr_state"].nunique()),
    })

@app.route("/api/grade_stats")
def grade_stats():
    g = df.groupby("grade").agg(
        count=("loan_amnt","count"), avg_int=("int_rate","mean"),
        avg_loan=("loan_amnt","mean"), default_rate=("default","mean")
    ).reset_index()
    g["default_rate"]=(g["default_rate"]*100).round(2); g["avg_int"]=g["avg_int"].round(2); g["avg_loan"]=g["avg_loan"].round(0)
    g["grade"]=pd.Categorical(g["grade"],["A","B","C","D","E"],ordered=True)
    return jsonify(g.sort_values("grade").to_dict(orient="records"))

@app.route("/api/state_stats")
def state_stats():
    s = df.groupby("addr_state").agg(
        count=("loan_amnt","count"), total_amount=("loan_amnt","sum"),
        avg_loan=("loan_amnt","mean"), avg_int=("int_rate","mean"),
        avg_dti=("dti","mean"), default_rate=("default","mean"),
        unemployment=("unemployment_rate","mean"), gdp_growth=("gdp_growth","mean")
    ).reset_index()
    s["default_rate"]=(s["default_rate"]*100).round(2); s["avg_loan"]=s["avg_loan"].round(0)
    s["avg_int"]=s["avg_int"].round(2); s["avg_dti"]=s["avg_dti"].round(2)
    s["unemployment"]=s["unemployment"].round(4); s["gdp_growth"]=s["gdp_growth"].round(4)
    s["state_name"]=s["addr_state"].map(STATE_NAMES).fillna(s["addr_state"])
    return jsonify(s.sort_values("count",ascending=False).to_dict(orient="records"))

@app.route("/api/int_rate_distribution")
def int_rate_dist():
    bins=list(range(6,30,2)); labels=[f"{b}–{b+2}%" for b in bins[:-1]]
    hist,_=np.histogram(df["int_rate"],bins=bins)
    df2=df.copy(); df2["bin"]=pd.cut(df2["int_rate"],bins=bins,labels=labels,right=False)
    dr=df2.groupby("bin",observed=True)["default"].mean().fillna(0)*100
    return jsonify({"labels":labels,"counts":hist.tolist(),"default_rates":dr.round(2).tolist()})

@app.route("/api/dti_distribution")
def dti_dist():
    bins=[0,5,10,15,20,25,30,40,65]; labels=["0–5","5–10","10–15","15–20","20–25","25–30","30–40","40+"]
    df2=df.copy(); df2["bin"]=pd.cut(df2["dti"],bins=bins,labels=labels,right=False)
    res=df2.groupby("bin",observed=True).agg(count=("dti","count"),default_rate=("default","mean")).reset_index()
    res["default_rate"]=(res["default_rate"]*100).round(2)
    return jsonify(res.to_dict(orient="records"))

@app.route("/api/revol_util_distribution")
def revol_dist():
    bins=list(range(0,110,10)); labels=[f"{b}–{b+10}%" for b in bins[:-1]]
    df2=df.copy(); df2["bin"]=pd.cut(df2["revol_util"].clip(0,100),bins=bins,labels=labels,right=False)
    res=df2.groupby("bin",observed=True).agg(count=("revol_util","count"),avg_int=("int_rate","mean")).reset_index()
    res["avg_int"]=res["avg_int"].round(2)
    return jsonify(res.to_dict(orient="records"))

@app.route("/api/income_cat_stats")
def income_cat_stats():
    res=df.groupby("income_label").agg(
        count=("loan_amnt","count"), avg_loan=("loan_amnt","mean"),
        avg_int=("int_rate","mean"), avg_dti=("dti","mean"), default_rate=("default","mean")
    ).reset_index()
    res["default_rate"]=(res["default_rate"]*100).round(2); res["avg_loan"]=res["avg_loan"].round(0)
    res["avg_int"]=res["avg_int"].round(2); res["avg_dti"]=res["avg_dti"].round(2)
    order=list(INCOME_CAT_MAP.values())
    res["income_label"]=pd.Categorical(res["income_label"],order,ordered=True)
    return jsonify(res.sort_values("income_label").to_dict(orient="records"))

@app.route("/api/emp_length_stats")
def emp_length_stats():
    res=df.groupby("emp_length_num").agg(
        count=("loan_amnt","count"), avg_loan=("loan_amnt","mean"),
        avg_int=("int_rate","mean"), default_rate=("default","mean")
    ).reset_index().sort_values("emp_length_num")
    res["default_rate"]=(res["default_rate"]*100).round(2); res["avg_int"]=res["avg_int"].round(2)
    return jsonify(res.to_dict(orient="records"))

@app.route("/api/macro_stats")
def macro_stats():
    m=df.groupby("addr_state")[["unemployment_rate","inflation","gdp_growth"]].mean().reset_index().round(4)
    m["state_name"]=m["addr_state"].map(STATE_NAMES).fillna(m["addr_state"])
    return jsonify(m.to_dict(orient="records"))

@app.route("/api/open_acc_stats")
def open_acc_stats():
    bins=[0,5,10,15,20,30,60]; labels=["0–5","5–10","10–15","15–20","20–30","30+"]
    df2=df.copy(); df2["bin"]=pd.cut(df2["open_acc"],bins=bins,labels=labels,right=False)
    res=df2.groupby("bin",observed=True).agg(count=("open_acc","count"),avg_int=("int_rate","mean")).reset_index()
    res["avg_int"]=res["avg_int"].round(2)
    return jsonify(res.to_dict(orient="records"))

if __name__ == "__main__":
    app.run(debug=True, port=5500)