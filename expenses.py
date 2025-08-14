import streamlit as st
import os, io, json, uuid
from datetime import datetime

# Firebase imports
try:
    import firebase_admin
    from firebase_admin import credentials, firestore
    FIREBASE_AVAILABLE = True
except:
    FIREBASE_AVAILABLE = False

# ReportLab
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4, landscape

# ---------------- Configuration ----------------
SERVICE_ACCOUNT_PATH = "serviceAccountKey.json"
FIRESTORE_COLLECTION = "independence_day_attendees"
LOCAL_DB_FILE = "local_attendees.json"
EVENT_NAME = "Independence Day"

# ---------------- Firebase helpers ----------------
def init_firebase():
    if not FIREBASE_AVAILABLE:
        return None
    try:
        if os.path.exists(SERVICE_ACCOUNT_PATH):
            cred = credentials.Certificate(SERVICE_ACCOUNT_PATH)
            if not firebase_admin._apps:
                firebase_admin.initialize_app(cred)
            return firestore.client()
        return None
    except Exception as e:
        st.warning(f"Firebase init failed: {e}")
        return None

def save_to_firestore(db, doc):
    ref = db.collection(FIRESTORE_COLLECTION).document()
    ref.set(doc)
    return ref.id

def read_from_firestore(db):
    coll = db.collection(FIRESTORE_COLLECTION)
    docs = coll.stream()
    return [{**d.to_dict(), "_id": d.id} for d in docs]

# ---------------- Local storage fallback ----------------
def load_local():
    if not os.path.exists(LOCAL_DB_FILE):
        return []
    try:
        with open(LOCAL_DB_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return []

def save_local(att):
    data = load_local()
    data.append(att)
    with open(LOCAL_DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# ---------------- PDF Generation ----------------
def generate_pass_pdf_bytes(attendee):
    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=landscape(A4))
    width, height = landscape(A4)

    c.setFont("Helvetica-Bold", 28)
    c.drawCentredString(width/2, height - 60, f"{EVENT_NAME} - Children's Pass")

    c.setFont("Helvetica", 12)
    c.drawRightString(width - 40, height - 40, f"Generated: {datetime.now().strftime('%d %b %Y %H:%M')}")

    box_x, box_y, box_w, box_h = 60, 120, width - 120, height - 220
    c.roundRect(box_x, box_y, box_w, box_h, 10, stroke=1, fill=0)

    left_x = box_x + 30
    y = box_y + box_h - 40
    gap = 30

    c.setFont("Helvetica-Bold", 20)
    c.drawString(left_x, y, attendee.get("name", "Unknown"))
    y -= gap

    c.setFont("Helvetica", 14)
    c.drawString(left_x, y, f"Class / Grade : {attendee.get('class', '-')}")
    y -= gap
    c.drawString(left_x, y, f"Age           : {attendee.get('age', '-')}")
    y -= gap
    c.drawString(left_x, y, f"Contact       : {attendee.get('contact', '-')}")
    y -= gap
    c.drawString(left_x, y, f"Reference     : {attendee.get('reference', '-')}")
    y -= gap

    c.setFont("Helvetica-Oblique", 12)
    notes = [
        "Please carry this pass during the event.",
        "Parents/Guardians must supervise children."
    ]
    for note in notes:
        c.drawString(left_x, y, "- " + note)
        y -= 18

    c.setFont("Helvetica", 12)
    c.drawString(width - 260, box_y + 30, "Authorized signature:")
    c.line(width - 260, box_y + 25, width - 90, box_y + 25)

    c.setFont("Helvetica-Bold", 10)
    c.drawCentredString(width/2, 30, f"{EVENT_NAME} • Organised by Your Organization")
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()

# ---------------- Streamlit UI ----------------
st.set_page_config(page_title="Independence Day - Attendees", layout="wide")
st.title("Independence Day — Children Registration & Pass Download")

# Firebase
db_client = init_firebase()
if db_client:
    st.success("Connected to Firebase")
else:
    st.info("Using local storage")

# Form to add attendee
with st.form("add_attendee", clear_on_submit=True):
    st.subheader("Register a child")
    col1, col2, col3 = st.columns(3)
    with col1:
        name = st.text_input("Child's Name")
        cls = st.text_input("Class / Grade")
    with col2:
        age = st.text_input("Age")
        contact = st.text_input("Parent Contact")
    with col3:
        reference = st.text_input("Reference (optional)")

    if st.form_submit_button("Save Attendee"):
        if not name.strip():
            st.error("Name is required")
        else:
            doc = {
                "name": name.strip(),
                "class": cls.strip(),
                "age": age.strip(),
                "contact": contact.strip(),
                "reference": reference.strip() or str(uuid.uuid4())[:8],
                "created_at": datetime.utcnow().isoformat()
            }
            if db_client:
                doc["_id"] = save_to_firestore(db_client, doc)
            else:
                save_local(doc)
            st.success(f"Saved attendee: {name}")

# Load attendees
if db_client:
    attendees = read_from_firestore(db_client)
else:
    attendees = load_local()

if attendees:
    import pandas as pd
    df = pd.DataFrame(attendees)
    st.dataframe(df)

    selected_ids = st.multiselect(
        "Select children to download passes",
        options=[a.get("_id", a.get("reference")) for a in attendees],
        format_func=lambda x: next((a['name'] for a in attendees if a.get("_id", a.get("reference"))==x), x)
    )

    if st.button("Generate & Download Passes"):
        for att in attendees:
            if att.get("_id", att.get("reference")) in selected_ids:
                pdf_bytes = generate_pass_pdf_bytes(att)
                st.download_button(
                    label=f"Download {att['name']}'s Pass",
                    data=pdf_bytes,
                    file_name=f"{att['name']}_pass.pdf",
                    mime="application/pdf"
                )
else:
    st.info("No attendees yet. Add some above.")

