import sqlite3
from datetime import date, timedelta, datetime
from pathlib import Path
import pandas as pd
import streamlit as st



def recommend_discount(risk, unsold, stock):
    """Rule-based discount recommendation using ML forecast risk."""
    if risk == "Expired":
        return None

    if stock <= 0:
        return 0

    unsold_ratio = unsold / stock

    if risk == "High" or unsold_ratio > 0.5:
        return 25
    elif risk == "Medium" or unsold_ratio > 0.2:
        return 15
    else:
        return 0


st.set_page_config(page_title="FreshGuard AI", page_icon="🥬", layout="wide")
DB = Path(__file__).with_name("freshguard.db")

def connect():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init_db():
    with connect() as c:
        c.execute("""CREATE TABLE IF NOT EXISTS products(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL, category TEXT NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity>=0),
            price REAL NOT NULL CHECK(price>=0),
            cost REAL NOT NULL CHECK(cost>=0),
            expiry TEXT NOT NULL, discount INTEGER NOT NULL DEFAULT 0
        )""")
        c.execute("""CREATE TABLE IF NOT EXISTS sales(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            quantity INTEGER NOT NULL CHECK(quantity>0),
            sold_at TEXT NOT NULL,
            unit_price REAL NOT NULL,
            FOREIGN KEY(product_id) REFERENCES products(id)
        )""")

def query(sql, params=()):
    with connect() as c:
        return pd.read_sql_query(sql, c, params=params)

def execute(sql, params=()):
    with connect() as c:
        c.execute(sql, params)

def seed():
    if not query("SELECT id FROM products LIMIT 1").empty:
        return
    items = [
        ("Milk","Dairy",50,3.00,1.80,3),
        ("Bread","Bakery",35,2.50,1.20,2),
        ("Yogurt","Dairy",70,1.75,0.95,5),
        ("Bananas","Produce",90,0.65,0.30,4),
        ("Eggs","Dairy",48,4.20,2.70,12),
        ("Spinach","Produce",32,2.80,1.40,2),
        ("Rice","Pantry",100,6.50,4.00,120),
    ]
    with connect() as c:
        for name,cat,qty,price,cost,days in items:
            cur=c.execute("INSERT INTO products(name,category,quantity,price,cost,expiry) VALUES (?,?,?,?,?,?)",
                          (name,cat,qty,price,cost,(date.today()+timedelta(days=days)).isoformat()))
            pid=cur.lastrowid
            # Simulated history for a classroom demonstration.
            base={"Milk":10,"Bread":12,"Yogurt":7,"Bananas":14,"Eggs":5,"Spinach":6,"Rice":2}[name]
            for days_ago in range(21,0,-1):
                n=max(1,base+((days_ago*7+pid*3)%7)-3)
                c.execute("INSERT INTO sales(product_id,quantity,sold_at,unit_price) VALUES (?,?,?,?)",
                          (pid,n,(date.today()-timedelta(days=days_ago)).isoformat(),price))

def inventory():
    return query("SELECT * FROM products ORDER BY expiry, name")

def history():
    return query("""SELECT s.*, p.name FROM sales s
                    JOIN products p ON s.product_id=p.id ORDER BY s.sold_at DESC, s.id DESC""")


def forecasts():
    from ml_model import predict_daily_sales

    products = inventory()
    sales = history()
    rows = []
    today = date.today()

    for p in products.to_dict("records"):
        product_id = int(p["id"])
        stock = int(p["quantity"])
        days_left = (
            date.fromisoformat(str(p["expiry"])) - today
        ).days

        prediction, method, mae = predict_daily_sales(
            sales, product_id
        )

        prediction = max(0.0, float(prediction))

        if days_left <= 0:
            unsold = stock
            risk = "Expired"
        else:
            unsold = max(
                0.0,
                stock - prediction * days_left
            )
            unsold = min(stock, unsold)

            ratio = unsold / stock if stock > 0 else 0

            if ratio > 0.5:
                risk = "High"
            elif ratio > 0.2:
                risk = "Medium"
            else:
                risk = "Low"

        rows.append({
            **p,
            "days_left": days_left,
            "daily_forecast": round(prediction, 2),
            "unsold": round(unsold, 2),
            "risk": risk,
            "at_risk_value": round(
                unsold * float(p["cost"]), 2
            ),
            "method": method,
            "validation_mae": mae
        })

    return pd.DataFrame(rows)


init_db()
seed()
st.sidebar.title("🥬 FreshGuard AI")
st.sidebar.caption("Smart grocery and food waste management")
page=st.sidebar.radio("Navigate",["Dashboard","Inventory","Sales","AI Predictions","Expiry Alerts","Reports"])
st.sidebar.divider()
st.sidebar.caption("Prototype • Local SQLite database")
st.title(f"🥬 {page}")
st.caption("Demo data is simulated. Forecasts use a Random Forest model when sufficient history is available, with a fallback for limited data.")

if page=="Dashboard":
    f=forecasts()
    a,b,c,d=st.columns(4)
    a.metric("Products",len(f))
    b.metric("Stock units",int(f["quantity"].sum()))
    c.metric("High / expired alerts",int(f["risk"].isin(["High","Expired"]).sum()))
    d.metric("Estimated at-risk cost",f"${f['at_risk_value'].sum():,.2f}")
    st.subheader("Products requiring attention")
    st.dataframe(f[["name","quantity","expiry","days_left","risk","unsold","at_risk_value"]],
                 use_container_width=True,hide_index=True)
    st.info("Try Inventory → Sales → AI Predictions → Expiry Alerts for the complete business workflow.")

elif page=="Inventory":
    st.subheader("Add a product")
    with st.form("add_product",clear_on_submit=True):
        a,b,c=st.columns(3)
        name=a.text_input("Product name")
        category=b.selectbox("Category",["Dairy","Bakery","Produce","Pantry","Other"])
        quantity=c.number_input("Quantity",min_value=0,step=1,value=20)
        d,e,f=st.columns(3)
        price=d.number_input("Selling price ($)",min_value=0.0,step=.25,value=3.0)
        cost=e.number_input("Unit cost ($)",min_value=0.0,step=.25,value=1.5)
        expiry=f.date_input("Expiry date",value=date.today()+timedelta(days=7))
        if st.form_submit_button("Add product",type="primary"):
            if not name.strip():
                st.error("Enter a product name.")
            elif cost>price:
                st.warning("Unit cost exceeds selling price. Product was saved; check pricing.")
                execute("INSERT INTO products(name,category,quantity,price,cost,expiry) VALUES(?,?,?,?,?,?)",
                        (name.strip(),category,int(quantity),float(price),float(cost),expiry.isoformat()))
                st.success("Product added."); st.rerun()
            else:
                execute("INSERT INTO products(name,category,quantity,price,cost,expiry) VALUES(?,?,?,?,?,?)",
                        (name.strip(),category,int(quantity),float(price),float(cost),expiry.isoformat()))
                st.success("Product added."); st.rerun()
    st.subheader("Current inventory")
    df=inventory()
    price_df = df.copy()

    price_df["Final Price"] = (
        price_df["price"] *
        (1 - price_df["discount"] / 100)
    ).round(2)

    price_df = price_df.rename(columns={
        "name": "Product",
        "category": "Category",
        "quantity": "Stock",
        "price": "Original Price",
        "discount": "Discount (%)",
        "expiry": "Expiry Date"
    })

    st.dataframe(
        price_df[[
            "Product", "Category", "Stock",
            "Original Price", "Discount (%)",
            "Final Price", "Expiry Date"
        ]],
        hide_index=True,
        width="stretch"
    )
    if not df.empty:
        with st.expander("Edit or remove a product"):
            labels={int(r.id):f"{r['name']} (ID {r.id})" for _,r in df.iterrows()}
            pid=st.selectbox("Choose product",list(labels),format_func=lambda x:labels[x])
            row=df[df.id==pid].iloc[0]
            with st.form(f"edit_{pid}"):
                newqty=st.number_input("Stock quantity",min_value=0,value=int(row.quantity))
                newprice=st.number_input("Selling price",min_value=0.0,value=float(row.price))
                newexpiry=st.date_input("Expiry date",value=date.fromisoformat(row.expiry))
                save=st.form_submit_button("Save changes")
                if save:
                    execute("UPDATE products SET quantity=?,price=?,expiry=? WHERE id=?",
                            (int(newqty),float(newprice),newexpiry.isoformat(),pid))
                    st.success("Updated."); st.rerun()
            if st.button("Remove product",help="Only products with no sales history can be removed"):
                try:
                    execute("DELETE FROM products WHERE id=?",(pid,))
                    st.success("Removed."); st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Cannot remove a product with sales history. Set stock to zero instead.")

elif page=="Sales":
    df=inventory()
    st.subheader("Record a sale")
    if df.empty:
        st.warning("Add products in Inventory first.")
    else:
        opts={int(r.id):f"{r['name']} — {r.quantity} in stock" for _,r in df.iterrows()}
        pid=st.selectbox("Product",list(opts),format_func=lambda x:opts[x])
        p=df[df.id==pid].iloc[0]
        qty=st.number_input("Units sold",min_value=1,step=1,value=1)
        if st.button("Complete sale",type="primary"):
            with connect() as c:
                current=c.execute("SELECT quantity,price,discount FROM products WHERE id=?",(pid,)).fetchone()
                if qty>current["quantity"]:
                    st.error("Not enough inventory to complete the sale.")
                else:
                    unit_price=round(current["price"]*(1-current["discount"]/100),2)
                    c.execute("UPDATE products SET quantity=quantity-? WHERE id=?",(int(qty),pid))
                    c.execute("INSERT INTO sales(product_id,quantity,sold_at,unit_price) VALUES(?,?,?,?)",
                              (pid,int(qty),date.today().isoformat(),unit_price))
                    st.success(f"Sale recorded: {qty} units for ${qty*unit_price:.2f}. Inventory updated.")

            st.rerun()
    st.subheader("Recent transactions")
    st.dataframe(history().head(30)[["name","quantity","sold_at","unit_price"]],
                 use_container_width=True,hide_index=True)

elif page=="AI Predictions":
    st.subheader("Machine Learning Sales Predictions")
    st.write(
        "Random Forest predicts daily sales using historical sales patterns. "
        "Products with insufficient history use a fallback method."
    )

    f = forecasts()

    display = f[[
        "name", "quantity", "days_left",
        "daily_forecast", "unsold", "risk",
        "method", "validation_mae"
    ]].copy()

    display = display.rename(columns={
        "name": "Product",
        "quantity": "Available Stock",
        "days_left": "Days Until Expiry",
        "daily_forecast": "Predicted Daily Sales",
        "unsold": "Potential Unsold",
        "risk": "Risk Level",
        "method": "Prediction Method",
        "validation_mae": "Validation MAE"
    })

    display["Risk Level"] = display["Risk Level"].map({
        "High": "🔴 High",
        "Medium": "🟠 Medium",
        "Low": "🟢 Low",
        "Expired": "⚫ Expired"
    }).fillna(display["Risk Level"])

    st.dataframe(
        display,
        hide_index=True,
        width="stretch"
    )

    st.subheader("Potential Unsold Inventory")
    st.bar_chart(f.set_index("name")["unsold"])

    st.caption(
        "Predictions are estimates based on simulated sales data. "
        "Validation MAE is measured in units sold per day."
    )

elif page=="Expiry Alerts":
    st.subheader("ML-Based Expiry Risk & Discount Management")

    f = forecasts()
    alerts = f[f["risk"].isin(
        ["High", "Medium", "Expired"]
    )].copy()

    st.subheader("Products Requiring Attention")

    if alerts.empty:
        st.success("No current expiry alerts.")
    else:
        display = alerts[[
            "name", "expiry", "days_left",
            "risk", "unsold", "discount"
        ]].rename(columns={
            "name": "Product",
            "expiry": "Expiry Date",
            "days_left": "Days Remaining",
            "risk": "Risk Level",
            "unsold": "Predicted Unsold",
            "discount": "Current Discount (%)"
        })

        st.dataframe(
            display,
            hide_index=True,
            width="stretch"
        )

        labels = {
            int(r["id"]): r["name"]
            for _, r in alerts.iterrows()
        }

        pid = st.selectbox(
            "Select product to review",
            list(labels),
            format_func=lambda x: labels[x]
        )

        p = alerts[alerts["id"] == pid].iloc[0]

        risk = p["risk"]
        stock = int(p["quantity"])
        unsold = float(p["unsold"])
        original_price = float(p["price"])
        current_discount = int(p["discount"])

        st.write(f"**ML Risk:** {risk}")
        st.write(f"**Predicted unsold stock:** {unsold:.0f} units")
        st.write(f"**Days until expiry:** {int(p['days_left'])}")

        if risk == "Expired":
            st.error(
                "This product has expired. Do not sell it."
            )
        else:
            suggested = recommend_discount(
                risk, unsold, stock
            )

            st.write(
                f"**Recommended discount:** {suggested}%"
            )
            st.write(
                f"**Original price:** ${original_price:.2f}"
            )

            discount = st.slider(
                "Manager-approved discount (%)",
                min_value=0,
                max_value=50,
                value=current_discount,
                step=5
            )

            final_price = original_price * (1 - discount / 100)

            st.metric(
                "Final selling price",
                f"${final_price:.2f}"
            )

            if st.button(
                "Approve and Update Price",
                type="primary"
            ):
                execute(
                    "UPDATE products SET discount=? WHERE id=?",
                    (discount, int(pid))
                )

                st.success(
                    f"Discount saved: {discount}%"
                )
                st.rerun()

    st.caption(
        "Discounts are rule-based recommendations informed "
        "by ML forecasts. Manager approval is required."
    )

elif page=="Reports":
    f=forecasts()
    s=history()
    st.subheader("Inventory risk report")
    st.bar_chart(f.set_index("name")["at_risk_value"])
    st.download_button("Download inventory risk CSV",data=f.to_csv(index=False),
                       file_name="freshguard_risk_report.csv",mime="text/csv")
    if not s.empty:
        st.subheader("Historical units sold by day")
        daily=s.groupby("sold_at",as_index=False)["quantity"].sum().sort_values("sold_at")
        st.line_chart(daily.set_index("sold_at")["quantity"])
        st.download_button("Download sales CSV",data=s.to_csv(index=False),
                           file_name="freshguard_sales.csv",mime="text/csv")
    st.caption("At-risk value uses unit cost, not selling price. Forecasts are estimates, not guaranteed losses.")
