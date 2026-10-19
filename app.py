
# ============================================================
# نظام إدارة الطيران
# Python + Streamlit + SQLite + Pandas
# ============================================================

import sqlite3
from pathlib import Path
from datetime import date

import pandas as pd
import streamlit as st


# ------------------------------------------------------------
# 1. إعداد صفحة التطبيق
# ------------------------------------------------------------

st.set_page_config(
    page_title="نظام إدارة الطيران",
    page_icon="✈️",
    layout="wide",
)

DB_PATH = Path(__file__).with_name("flights.db")

COUNTRIES = ["اليمن", "السعودية", "الإمارات", "قطر"]
CURRENCIES = ["USD", "SAR", "YER", "AED", "QAR"]

BOARDING = [
    "لم يصعد بعد",
    "صعد إلى الطائرة",
    "لم يسافر",
    "أُلغي سفره",
]

LOCATIONS = [
    "صالة الانتظار",
    "بوابة الصعود",
    "داخل الطائرة",
    "خارج إجراءات السفر",
]

BOOKINGS = [
    "مؤكد",
    "قيد التأكيد",
    "على قائمة الانتظار",
    "ملغى",
]


# ------------------------------------------------------------
# 2. الاتصال بقاعدة البيانات
# ------------------------------------------------------------

def connect():
    """فتح اتصال بقاعدة SQLite."""
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys = ON")
    return con


def execute(sql, params=()):
    """تنفيذ أمر إضافة أو تعديل أو حذف."""
    with connect() as con:
        cursor = con.execute(sql, params)
        return cursor.lastrowid


def read_data(sql, params=()):
    """قراءة البيانات وإرجاعها في جدول Pandas."""
    with connect() as con:
        return pd.read_sql_query(sql, con, params=params)


# ------------------------------------------------------------
# 3. إنشاء جداول قاعدة البيانات
# ------------------------------------------------------------

def initialize_database():
    """إنشاء الجداول تلقائيًا عند أول تشغيل."""

    with connect() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS flights (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                flight_code TEXT NOT NULL,
                origin TEXT NOT NULL,
                destination TEXT NOT NULL,
                flight_date TEXT NOT NULL,
                currency TEXT NOT NULL,
                fare REAL NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS passengers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                phone TEXT DEFAULT '',
                passport TEXT DEFAULT '',
                flight_id INTEGER NOT NULL,
                fare REAL NOT NULL DEFAULT 0,
                boarding TEXT NOT NULL,
                location TEXT NOT NULL,
                booking TEXT NOT NULL,
                FOREIGN KEY (flight_id)
                    REFERENCES flights(id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                passenger_id INTEGER NOT NULL,
                kind TEXT NOT NULL,
                amount REAL NOT NULL,
                method TEXT NOT NULL,
                transaction_date TEXT NOT NULL,
                note TEXT DEFAULT '',
                FOREIGN KEY (passenger_id)
                    REFERENCES passengers(id)
                    ON DELETE CASCADE
            );
        """)


# ------------------------------------------------------------
# 4. حساب حالة الدفع
# ------------------------------------------------------------

def get_payment_status(fare, paid, refunded):
    """تحديد حالة الدفع من المبالغ المسجلة."""

    net_paid = paid - refunded

    if refunded > 0 and net_paid <= 0:
        return "مسترد"

    if net_paid <= 0:
        return "غير مدفوع"

    if net_paid < fare:
        return "مدفوع جزئيًا"

    return "مدفوع بالكامل"


def get_payment_totals(passenger_id):
    """حساب مجموع الدفعات والاستردادات لمسافر واحد."""

    data = read_data("""
        SELECT
            COALESCE(
                SUM(CASE WHEN kind = 'دفعة'
                    THEN amount ELSE 0 END), 0
            ) AS paid,

            COALESCE(
                SUM(CASE WHEN kind = 'استرداد'
                    THEN amount ELSE 0 END), 0
            ) AS refunded

        FROM transactions
        WHERE passenger_id = ?
    """, (passenger_id,))

    paid = float(data.iloc[0]["paid"])
    refunded = float(data.iloc[0]["refunded"])

    return paid, refunded


# ------------------------------------------------------------
# 5. تحميل المسافرين مع حساباتهم المالية
# ------------------------------------------------------------

def load_passengers():

    data = read_data("""
        SELECT
            p.*,
            f.flight_code,
            f.origin,
            f.destination,
            f.flight_date,
            f.currency,

            COALESCE((
                SELECT SUM(t.amount)
                FROM transactions t
                WHERE t.passenger_id = p.id
                AND t.kind = 'دفعة'
            ), 0) AS total_paid,

            COALESCE((
                SELECT SUM(t.amount)
                FROM transactions t
                WHERE t.passenger_id = p.id
                AND t.kind = 'استرداد'
            ), 0) AS total_refunded

        FROM passengers p
        JOIN flights f ON f.id = p.flight_id
        ORDER BY p.id DESC
    """)

    if not data.empty:

        data["net_paid"] = (
            data["total_paid"] - data["total_refunded"]
        )

        data["remaining"] = (
            data["fare"] - data["net_paid"]
        ).clip(lower=0)

        data["payment_status"] = data.apply(
            lambda row: get_payment_status(
                row["fare"],
                row["total_paid"],
                row["total_refunded"],
            ),
            axis=1,
        )

    return data


def money(value, currency):
    """تنسيق المبلغ مع رمز العملة."""
    return f"{float(value):,.2f} {currency}"


# تهيئة قاعدة البيانات عند تشغيل التطبيق
initialize_database()


# ------------------------------------------------------------
# 6. تصميم الواجهة
# ------------------------------------------------------------

st.markdown("""
<style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }

    div[data-testid="stMetric"] {
        background: rgba(120, 130, 150, 0.08);
        border: 1px solid rgba(120, 130, 150, 0.18);
        padding: 14px;
        border-radius: 12px;
    }
</style>
""", unsafe_allow_html=True)

st.title("✈️ نظام إدارة الطيران")
st.caption("إدارة الرحلات والمسافرين والمدفوعات")


# ------------------------------------------------------------
# 7. القائمة الرئيسية
# ------------------------------------------------------------

with st.sidebar:
    st.title("إدارة الطيران")

    page = st.radio(
        "اختر القسم",
        [
            "لوحة التحكم",
            "الرحلات",
            "المسافرون",
            "المدفوعات",
            "التقارير",
        ],
    )

    st.divider()
    st.caption("إصدار أولي لإدارة الرحلات والسجلات")


# ------------------------------------------------------------
# 8. لوحة التحكم
# ------------------------------------------------------------

if page == "لوحة التحكم":

    flights = read_data("SELECT * FROM flights")
    passengers = load_passengers()

    st.header("لوحة التحكم")

    total = len(passengers)

    boarded = (
        int((passengers["boarding"] == "صعد إلى الطائرة").sum())
        if total else 0
    )

    waiting = (
        int((passengers["location"] == "صالة الانتظار").sum())
        if total else 0
    )

    unpaid = (
        int(passengers["payment_status"].isin(
            ["غير مدفوع", "مدفوع جزئيًا"]
        ).sum())
        if total else 0
    )

    a, b, c, d = st.columns(4)

    a.metric("إجمالي المسافرين", total)
    b.metric("صعدوا للطائرة", boarded)
    c.metric("في صالة الانتظار", waiting)
    d.metric("عليهم مبالغ مستحقة", unpaid)

    st.metric("عدد الرحلات", len(flights))

    if not passengers.empty:

        st.subheader("الملخص المالي حسب العملة")

        for currency in sorted(passengers["currency"].unique()):

            group = passengers[
                passengers["currency"] == currency
            ]

            total_fares = group["fare"].sum()

            net_collected = (
                group["total_paid"].sum()
                - group["total_refunded"].sum()
            )

            remaining = group["remaining"].sum()

            a, b, c = st.columns(3)

            a.metric(
                f"قيمة التذاكر · {currency}",
                money(total_fares, currency),
            )

            b.metric(
                f"صافي المقبوض · {currency}",
                money(net_collected, currency),
            )

            c.metric(
                f"المتبقي · {currency}",
                money(remaining, currency),
            )

        st.subheader("أحدث المسافرين")

        st.dataframe(
            passengers[[
                "full_name",
                "flight_code",
                "origin",
                "destination",
                "boarding",
                "location",
                "booking",
                "payment_status",
            ]],
            use_container_width=True,
            hide_index=True,
        )

    else:
        st.info("أنشئ رحلة ثم أضف المسافرين لعرض الإحصاءات.")


# ------------------------------------------------------------
# 9. إدارة الرحلات
# ------------------------------------------------------------

elif page == "الرحلات":

    st.header("إدارة الرحلات")

    flights = read_data(
        "SELECT * FROM flights ORDER BY flight_date DESC"
    )

    with st.expander("➕ إنشاء رحلة جديدة", expanded=True):

        with st.form("new_flight"):

            code = st.text_input(
                "رقم الرحلة",
                placeholder="مثال: FL-101",
            )

            a, b = st.columns(2)

            origin = a.selectbox(
                "بلد المغادرة",
                COUNTRIES,
            )

            destinations = [
                country for country in COUNTRIES
                if country != origin
            ]

            destination = b.selectbox(
                "بلد الوصول",
                destinations,
            )

            c, d = st.columns(2)

            flight_date = c.date_input(
                "تاريخ الرحلة",
                value=date.today(),
            )

            currency = d.selectbox(
                "عملة التذكرة",
                CURRENCIES,
            )

            fare = st.number_input(
                "السعر الافتراضي للتذكرة",
                min_value=0.0,
                value=0.0,
                step=10.0,
            )

            submit = st.form_submit_button(
                "حفظ الرحلة",
                type="primary",
                use_container_width=True,
            )

            if submit:

                if not code.strip():
                    st.error("رقم الرحلة مطلوب.")

                else:
                    execute("""
                        INSERT INTO flights
                        (
                            flight_code,
                            origin,
                            destination,
                            flight_date,
                            currency,
                            fare
                        )
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        code.strip(),
                        origin,
                        destination,
                        flight_date.isoformat(),
                        currency,
                        fare,
                    ))

                    st.success("تم إنشاء الرحلة بنجاح.")
                    st.rerun()

    flights = read_data(
        "SELECT * FROM flights ORDER BY flight_date DESC"
    )

    if not flights.empty:

        st.subheader("الرحلات المسجلة")

        st.dataframe(
            flights[[
                "id",
                "flight_code",
                "origin",
                "destination",
                "flight_date",
                "currency",
                "fare",
            ]],
            use_container_width=True,
            hide_index=True,
        )

        with st.expander("حذف رحلة"):

            labels = {
                int(row["id"]):
                f'{row["flight_code"]} | '
                f'{row["origin"]} ← {row["destination"]} | '
                f'{row["flight_date"]}'
                for _, row in flights.iterrows()
            }

            flight_id = st.selectbox(
                "اختر الرحلة",
                list(labels.keys()),
                format_func=lambda x: labels[x],
            )

            if st.button("حذف الرحلة المحددة"):

                linked = read_data(
                    "SELECT COUNT(*) AS n FROM passengers "
                    "WHERE flight_id = ?",
                    (flight_id,),
                ).iloc[0]["n"]

                if int(linked) > 0:
                    st.error(
                        "لا يمكن حذف رحلة مرتبطة بمسافرين. "
                        "احذف سجلات المسافرين أولًا."
                    )

                else:
                    execute(
                        "DELETE FROM flights WHERE id = ?",
                        (flight_id,),
                    )
                    st.success("تم حذف الرحلة.")
                    st.rerun()

    else:
        st.info("لا توجد رحلات مسجلة.")


# ------------------------------------------------------------
# 10. إدارة المسافرين
# ------------------------------------------------------------

elif page == "المسافرون":

    st.header("إدارة المسافرين")

    flights = read_data(
        "SELECT * FROM flights ORDER BY flight_date DESC"
    )

    if flights.empty:

        st.warning("أنشئ رحلة أولًا.")

    else:

        flight_labels = {
            int(row["id"]):
            f'{row["flight_code"]} | '
            f'{row["origin"]} → {row["destination"]} | '
            f'{row["flight_date"]}'
            for _, row in flights.iterrows()
        }

        with st.expander("➕ تسجيل مسافر جديد", expanded=True):

            with st.form("new_passenger"):

                name = st.text_input("اسم المسافر الكامل")
                phone = st.text_input("رقم الهاتف")
                passport = st.text_input("رقم الجواز")

                flight_id = st.selectbox(
                    "اختر الرحلة",
                    list(flight_labels.keys()),
                    format_func=lambda x: flight_labels[x],
                )

                selected_flight = flights[
                    flights["id"] == flight_id
                ].iloc[0]

                fare = st.number_input(
                    f'قيمة التذكرة ({selected_flight["currency"]})',
                    min_value=0.0,
                    value=float(selected_flight["fare"]),
                    step=10.0,
                )

                a, b = st.columns(2)

                boarding = a.selectbox(
                    "حالة الصعود",
                    BOARDING,
                )

                location = b.selectbox(
                    "موقع المسافر",
                    LOCATIONS,
                )

                booking = st.selectbox(
                    "حالة الحجز",
                    BOOKINGS,
                )

                submit = st.form_submit_button(
                    "حفظ المسافر",
                    type="primary",
                    use_container_width=True,
                )

                if submit:

                    if not name.strip():
                        st.error("اسم المسافر مطلوب.")

                    else:

                        execute("""
                            INSERT INTO passengers
                            (
                                full_name,
                                phone,
                                passport,
                                flight_id,
                                fare,
                                boarding,
                                location,
                                booking
                            )
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            name.strip(),
                            phone.strip(),
                            passport.strip(),
                            flight_id,
                            fare,
                            boarding,
                            location,
                            booking,
                        ))

                        st.success("تم تسجيل المسافر.")
                        st.rerun()

    passengers = load_passengers()

    if not passengers.empty:

        st.subheader("قائمة المسافرين")

        search = st.text_input(
            "🔎 البحث بالاسم أو رقم الجواز"
        )

        view = passengers.copy()

        if search.strip():

            mask = (
                view["full_name"].astype(str).str.contains(
                    search, case=False, na=False
                )
                |
                view["passport"].astype(str).str.contains(
                    search, case=False, na=False
                )
            )

            view = view[mask]

        a, b, c = st.columns(3)

        boarding_filter = a.selectbox(
            "تصفية الصعود",
            ["الكل"] + BOARDING,
        )

        location_filter = b.selectbox(
            "تصفية الموقع",
            ["الكل"] + LOCATIONS,
        )

        booking_filter = c.selectbox(
            "تصفية الحجز",
            ["الكل"] + BOOKINGS,
        )

        if boarding_filter != "الكل":
            view = view[
                view["boarding"] == boarding_filter
            ]

        if location_filter != "الكل":
            view = view[
                view["location"] == location_filter
            ]

        if booking_filter != "الكل":
            view = view[
                view["booking"] == booking_filter
            ]

        display = view[[
            "id",
            "full_name",
            "phone",
            "passport",
            "flight_code",
            "origin",
            "destination",
            "fare",
            "net_paid",
            "remaining",
            "payment_status",
            "boarding",
            "location",
            "booking",
        ]].rename(columns={
            "id": "رقم",
            "full_name": "اسم المسافر",
            "phone": "الهاتف",
            "passport": "الجواز",
            "flight_code": "رقم الرحلة",
            "origin": "من",
            "destination": "إلى",
            "fare": "قيمة التذكرة",
            "net_paid": "صافي المدفوع",
            "remaining": "المتبقي",
            "payment_status": "حالة الدفع",
            "boarding": "حالة الصعود",
            "location": "الموقع",
            "booking": "حالة الحجز",
        })

        st.dataframe(
            display,
            use_container_width=True,
            hide_index=True,
        )

        passenger_labels = {
            int(row["id"]):
            f'{row["full_name"]} — {row["flight_code"]}'
            for _, row in passengers.iterrows()
        }

        with st.expander("✏️ تعديل حالات المسافر"):

            with st.form("edit_passenger"):

                pid = st.selectbox(
                    "اختر المسافر",
                    list(passenger_labels.keys()),
                    format_func=lambda x: passenger_labels[x],
                )

                current = passengers[
                    passengers["id"] == pid
                ].iloc[0]

                a, b = st.columns(2)

                new_boarding = a.selectbox(
                    "حالة الصعود الجديدة",
                    BOARDING,
                    index=BOARDING.index(current["boarding"]),
                )

                new_location = b.selectbox(
                    "الموقع الجديد",
        