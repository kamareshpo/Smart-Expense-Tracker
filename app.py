from flask import Flask, render_template, redirect, url_for, request, flash, Response, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from collections import Counter
import os
import io
import csv

# Optional Excel support
try:
    import pandas as pd
except ImportError:
    pd = None

# ======================
# Configuration
# ======================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your_secret_key_here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///expenses.db'
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')
app.config['PROFILE_UPLOAD'] = os.path.join(app.config['UPLOAD_FOLDER'], 'profiles')
app.config['RECEIPT_UPLOAD'] = os.path.join(app.config['UPLOAD_FOLDER'], 'receipts')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif', 'pdf'}

os.makedirs(app.config['PROFILE_UPLOAD'], exist_ok=True)
os.makedirs(app.config['RECEIPT_UPLOAD'], exist_ok=True)

db = SQLAlchemy(app)

# ======================
# Models
# ======================
class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150))
    email = db.Column(db.String(150), unique=True)
    password = db.Column(db.String(256))
    profile_pic = db.Column(db.String(256), nullable=True)
    currency = db.Column(db.String(10), default='INR')
    language = db.Column(db.String(10), default='en')
    monthly_budget = db.Column(db.Float, default=0.0)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

class Tag(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True)
    transactions = db.relationship('Transaction', secondary='transaction_tags', back_populates='tags')

transaction_tags = db.Table('transaction_tags',
    db.Column('transaction_id', db.Integer, db.ForeignKey('transaction.id')),
    db.Column('tag_id', db.Integer, db.ForeignKey('tag.id'))
)

class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    type = db.Column(db.String(20))  # income or expense
    category = db.Column(db.String(50))
    amount = db.Column(db.Float)
    note = db.Column(db.String(256), nullable=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    payment_method = db.Column(db.String(50))
    is_recurring = db.Column(db.Boolean, default=False)
    recurring_period = db.Column(db.String(20), nullable=True)
    receipt = db.Column(db.String(256), nullable=True)
    tags = db.relationship('Tag', secondary=transaction_tags, back_populates='transactions')

# ======================
# Login Manager
# ======================
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ======================
# Helpers
# ======================
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

def save_file(fileobj, folder):
    if fileobj and allowed_file(fileobj.filename):
        filename = secure_filename(f"{int(datetime.utcnow().timestamp())}_{fileobj.filename}")
        path = os.path.join(folder, filename)
        fileobj.save(path)
        return filename
    return None

def validate_password_strength(password):
    if len(password) < 8: return False, "Password must be at least 8 characters"
    if not any(c.islower() for c in password): return False, "Password must include a lowercase letter"
    if not any(c.isupper() for c in password): return False, "Password must include an uppercase letter"
    if not any(c.isdigit() for c in password): return False, "Password must include a digit"
    if not any(c in "!@#$%^&*()-_=+[]{}|;:,.<>?/~`" for c in password): return False, "Password must include a special character"
    return True, ""

# ======================
# Routes
# ======================
@app.route("/")
def home():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET","POST"])
def register():
    if request.method == "POST":
        username = request.form["username"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if User.query.filter_by(email=email).first():
            flash("Email already registered", "danger")
            return redirect(url_for("register"))

        ok, msg = validate_password_strength(password)
        if not ok:
            flash(msg, "danger")
            return redirect(url_for("register"))

        user = User(username=username, email=email, password=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()
        flash("Registered! Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")

@app.route("/login", methods=["GET","POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password, password):
            login_user(user)
            flash("Logged in successfully!", "success")
            return redirect(url_for("dashboard"))
        flash("Invalid credentials", "danger")
    return render_template("login.html")

@app.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out", "info")
    return redirect(url_for("home"))

@app.route("/dashboard")
@login_required
def dashboard():
    transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.date.desc()).all()
    total_balance = sum(t.amount if t.type=='income' else -t.amount for t in transactions)

    cat_counter = Counter()
    for t in transactions:
        if t.type=='expense':
            cat_counter[t.category] += t.amount
    pie_labels = list(cat_counter.keys())
    pie_values = [cat_counter[k] for k in pie_labels]

    # Simple trend data for charts
    trend_labels = [t.date.strftime('%Y-%m') for t in transactions]
    trend_values = [t.amount if t.type=='expense' else 0 for t in transactions]
    income_trend = [t.amount if t.type=='income' else 0 for t in transactions]

    return render_template("dashboard.html",
                           transactions=transactions,
                           total_balance=total_balance,
                           pie_labels=pie_labels,
                           pie_values=pie_values,
                           trend_labels=trend_labels,
                           trend_values=trend_values,
                           income_trend=income_trend,
                           insights=[],
                           my_salary_total=sum(t.amount for t in transactions if t.category=="my_salary" and t.type=="income"),
                           family_salary_total=sum(t.amount for t in transactions if t.category=="family_salary" and t.type=="income"),
                           other_income_total=sum(t.amount for t in transactions if t.type=="income") - sum(t.amount for t in transactions if t.category in ["my_salary","family_salary"]),
                           expense_total=sum(t.amount for t in transactions if t.type=="expense")
                           )

@app.route("/add-transaction", methods=["GET","POST"])
@login_required
def add_transaction():
    if request.method=="POST":
        t_type = request.form.get("type")
        category = request.form.get("category")
        amount = float(request.form.get("amount",0))
        note = request.form.get("note","").strip()
        payment_method = request.form.get("payment_method")
        recurring = request.form.get("recurring")
        tags_raw = request.form.get("tags","")

        receipt_file = request.files.get("receipt")
        receipt_filename = save_file(receipt_file, app.config['RECEIPT_UPLOAD']) if receipt_file else None

        tx = Transaction(
            user_id=current_user.id,
            type=t_type,
            category=category,
            amount=abs(amount),
            note=note,
            payment_method=payment_method,
            is_recurring=(recurring!="" and recurring is not None),
            recurring_period=recurring if recurring else None,
            receipt=receipt_filename
        )

        if tags_raw:
            tags_list = [t.strip().lower() for t in tags_raw.split(",") if t.strip()]
            for tag_name in tags_list:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                tx.tags.append(tag)

        db.session.add(tx)
        db.session.commit()
        flash("Transaction added", "success")
        return redirect(url_for("dashboard"))

    return render_template("add_transaction.html")

# ======================
# CSV/Excel export
# ======================
@app.route("/export-csv")
@login_required
def export_csv():
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Date','Type','Category','Amount','Payment Method','Note','Tags'])
    for t in transactions:
        tags = ','.join([tag.name for tag in t.tags])
        writer.writerow([t.date.strftime('%Y-%m-%d'), t.type, t.category, t.amount, t.payment_method, t.note, tags])
    output.seek(0)
    return Response(output, mimetype="text/csv",
                    headers={"Content-Disposition":"attachment;filename=transactions.csv"})

@app.route("/export-excel")
@login_required
def export_excel():
    if not pd:
        flash("Pandas is required for Excel export.", "danger")
        return redirect(url_for("dashboard"))
    transactions = Transaction.query.filter_by(user_id=current_user.id).all()
    data = []
    for t in transactions:
        tags = ','.join([tag.name for tag in t.tags])
        data.append({
            "Date": t.date.strftime('%Y-%m-%d'),
            "Type": t.type,
            "Category": t.category,
            "Amount": t.amount,
            "Payment Method": t.payment_method,
            "Note": t.note,
            "Tags": tags
        })
    df = pd.DataFrame(data)
    output = io.BytesIO()
    df.to_excel(output, index=False)
    output.seek(0)
    return Response(output, mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    headers={"Content-Disposition":"attachment;filename=transactions.xlsx"})

# ======================
# Uploaded files
# ======================
@app.route('/uploads/<path:filename>')
@login_required
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# ======================
# Profile
# ======================
@app.route("/profile", methods=["GET","POST"])
@login_required
def profile():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        currency = request.form.get("currency")
        language = request.form.get("language")
        monthly_budget = float(request.form.get("monthly_budget",0))

        profile_pic_file = request.files.get("profile_pic")
        profile_pic_filename = save_file(profile_pic_file, app.config['PROFILE_UPLOAD']) if profile_pic_file else current_user.profile_pic

        current_user.username = username
        current_user.email = email
        current_user.currency = currency
        current_user.language = language
        current_user.monthly_budget = monthly_budget
        current_user.profile_pic = profile_pic_filename
        db.session.commit()
        flash("Profile updated", "success")
        return redirect(url_for("profile"))

    return render_template("profile.html")

# ======================
# Change password
# ======================
@app.route("/change-password", methods=["POST"])
@login_required
def change_password():
    old = request.form.get("old_password")
    new = request.form.get("new_password")
    if not check_password_hash(current_user.password, old):
        flash("Old password is incorrect", "danger")
        return redirect(url_for("profile"))
    ok,msg = validate_password_strength(new)
    if not ok:
        flash(msg, "danger")
        return redirect(url_for("profile"))
    current_user.password = generate_password_hash(new)
    db.session.commit()
    flash("Password updated", "success")
    return redirect(url_for("profile"))

# ======================
# Edit/Delete transaction
# ======================
@app.route("/edit-transaction/<int:id>", methods=["GET","POST"])
@login_required
def edit_transaction(id):
    tx = Transaction.query.get_or_404(id)
    if tx.user_id != current_user.id:
        flash("Not authorized", "danger")
        return redirect(url_for("dashboard"))

    if request.method=="POST":
        tx.type = request.form.get("type")
        tx.category = request.form.get("category")
        tx.amount = float(request.form.get("amount",0))
        tx.note = request.form.get("note","").strip()
        tx.payment_method = request.form.get("payment_method")
        recurring = request.form.get("recurring")
        tx.is_recurring = recurring!="" and recurring is not None
        tx.recurring_period = recurring if recurring else None

        receipt_file = request.files.get("receipt")
        if receipt_file:
            tx.receipt = save_file(receipt_file, app.config['RECEIPT_UPLOAD'])

        tags_csv = request.form.get("tags","")
        tx.tags.clear()
        if tags_csv:
            for tag_name in [t.strip().lower() for t in tags_csv.split(",") if t.strip()]:
                tag = Tag.query.filter_by(name=tag_name).first()
                if not tag:
                    tag = Tag(name=tag_name)
                    db.session.add(tag)
                tx.tags.append(tag)
        db.session.commit()
        flash("Transaction updated", "success")
        return redirect(url_for("dashboard"))

    tags_csv = ",".join([tag.name for tag in tx.tags])
    return render_template("edit_transaction.html", transaction=tx, tags_csv=tags_csv)

@app.route("/delete-transaction/<int:id>")
@login_required
def delete_transaction(id):
    tx = Transaction.query.get_or_404(id)
    if tx.user_id != current_user.id:
        flash("Not authorized", "danger")
        return redirect(url_for("dashboard"))
    db.session.delete(tx)
    db.session.commit()
    flash("Transaction deleted", "info")
    return redirect(url_for("dashboard"))

# ======================
# Email report stub
# ======================
@app.route("/send-report-now")
@login_required
def send_report_now():
    flash("Email report functionality not configured yet.", "info")
    return redirect(url_for("dashboard"))

@app.route("/pay", methods=["GET", "POST"])
def pay():
    if request.method == "POST":
        amount = request.form.get("amount")
        # Simulate a successful payment
        # Save it in your DB if needed
        return f"Payment of ₹{amount} successful! 🎉"
    return render_template("pay.html")


# ======================
# Run app
# ======================
if __name__ == "__main__":
    # Make sure folders exist
    os.makedirs(app.config['PROFILE_UPLOAD'], exist_ok=True)
    os.makedirs(app.config['RECEIPT_UPLOAD'], exist_ok=True)

    # Create database tables inside app context
    with app.app_context():
        db.create_all()

    # Run the app
    app.run(debug=True)
    