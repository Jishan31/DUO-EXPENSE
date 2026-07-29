from datetime import datetime, date
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from extensions import db, login_manager


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    phone = db.Column(db.String(20), unique=True, nullable=True)
    password_hash = db.Column(db.String(255), nullable=False, default="")
    oauth_provider = db.Column(db.String(20), nullable=True)   # "google", "apple", or None for password accounts
    oauth_id = db.Column(db.String(255), nullable=True)         # the provider's unique subject/user id
    avatar_url = db.Column(db.String(255), default="")
    currency = db.Column(db.String(8), default="INR")
    dark_mode = db.Column(db.Boolean, default=False)
    monthly_budget_total = db.Column(db.Float, default=0.0)
    upi_id = db.Column(db.String(80), default="")
    business_name = db.Column(db.String(120), default="")
    business_gstin = db.Column(db.String(15), default="")
    role = db.Column(db.String(20), default="user")  # "user" or "auditor"
    region = db.Column(db.String(2), default="IN")  # ISO country code, drives phone number validation
    auditor_qualification = db.Column(db.String(200), default="")  # e.g. "Chartered Accountant"
    auditor_bio = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    categories = db.relationship("Category", backref="owner", lazy=True, cascade="all, delete-orphan")
    expenses = db.relationship("Expense", backref="owner", lazy=True, cascade="all, delete-orphan")
    incomes = db.relationship("Income", backref="owner", lazy=True, cascade="all, delete-orphan")
    loans = db.relationship("Loan", backref="owner", lazy=True, cascade="all, delete-orphan")
    products = db.relationship("Product", backref="owner", lazy=True, cascade="all, delete-orphan")
    clients = db.relationship("Client", backref="owner", lazy=True, cascade="all, delete-orphan")
    chat_messages = db.relationship("ChatMessage", backref="owner", lazy=True, cascade="all, delete-orphan")
    import_batches = db.relationship("ImportBatch", backref="owner", lazy=True, cascade="all, delete-orphan")
    filing_projects = db.relationship("FilingProject", backref="owner", lazy=True,
                                       cascade="all, delete-orphan", foreign_keys="FilingProject.user_id")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self.password_hash:
            return False  # OAuth-only account — no password set, sign in via Google/Apple instead
        return check_password_hash(self.password_hash, raw_password)


class Category(db.Model):
    __tablename__ = "categories"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    name = db.Column(db.String(60), nullable=False)
    icon = db.Column(db.String(40), default="tag")       # simple icon key used by the frontend
    color = db.Column(db.String(20), default="#B57EDC")   # sector color on the expense wheel
    monthly_budget = db.Column(db.Float, default=0.0)
    is_default = db.Column(db.Boolean, default=False)
    sort_order = db.Column(db.Integer, default=0)

    expenses = db.relationship("Expense", backref="category", lazy=True)

    def spent_this_month(self):
        today = date.today()
        total = 0.0
        for e in self.expenses:
            if e.date.year == today.year and e.date.month == today.month:
                total += e.amount
        return total


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today)
    time = db.Column(db.Time, nullable=True)
    payment_mode = db.Column(db.String(30), default="UPI")  # Cash, UPI, Debit Card, Credit Card, Bank Transfer
    description = db.Column(db.Text, default="")
    receipt_path = db.Column(db.String(255), default="")
    location = db.Column(db.String(120), default="")
    tags = db.Column(db.String(255), default="")
    merchant = db.Column(db.String(120), default="")
    gst_amount = db.Column(db.Float, default=0.0)
    import_batch_id = db.Column(db.Integer, db.ForeignKey("import_batches.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Income(db.Model):
    __tablename__ = "incomes"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    source = db.Column(db.String(30), nullable=False)  # Salary, Business, Freelancing, Investments, Others
    name = db.Column(db.String(120), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, default=date.today)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)          # e.g. "Home Loan" or "Bike EMI"
    loan_type = db.Column(db.String(40), default="Personal")   # Home, Vehicle, Personal, Education, Business, Credit Card, Other
    lender = db.Column(db.String(120), default="")              # bank / NBFC name
    principal_amount = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, default=0.0)             # annual %, reducing balance
    tenure_months = db.Column(db.Integer, nullable=False)
    start_date = db.Column(db.Date, default=date.today)
    monthly_emi = db.Column(db.Float, default=0.0)
    status = db.Column(db.String(20), default="active")          # active, closed
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    payments = db.relationship("LoanPayment", backref="loan", lazy=True,
                                cascade="all, delete-orphan", order_by="LoanPayment.due_date")

    def total_interest(self):
        return round(sum(p.interest_component for p in self.payments), 2)

    def principal_paid(self):
        return round(sum(p.principal_component for p in self.payments if p.is_paid), 2)

    def interest_paid(self):
        return round(sum(p.interest_component for p in self.payments if p.is_paid), 2)

    def amount_paid(self):
        return round(sum(p.amount for p in self.payments if p.is_paid), 2)

    def principal_remaining(self):
        return round(max(self.principal_amount - self.principal_paid(), 0), 2)

    def interest_remaining(self):
        return round(max(self.total_interest() - self.interest_paid(), 0), 2)

    def next_due(self):
        upcoming = [p for p in self.payments if not p.is_paid]
        return min(upcoming, key=lambda p: p.due_date) if upcoming else None

    def percent_paid(self):
        if not self.principal_amount:
            return 0
        return round(min(self.principal_paid() / self.principal_amount * 100, 100), 1)


class LoanPayment(db.Model):
    __tablename__ = "loan_payments"

    id = db.Column(db.Integer, primary_key=True)
    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id"), nullable=False)

    installment_no = db.Column(db.Integer, nullable=False)
    due_date = db.Column(db.Date, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    principal_component = db.Column(db.Float, default=0.0)
    interest_component = db.Column(db.Float, default=0.0)

    is_paid = db.Column(db.Boolean, default=False)
    paid_date = db.Column(db.Date, nullable=True)
    payment_mode = db.Column(db.String(30), default="")


class Product(db.Model):
    __tablename__ = "products"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    sku = db.Column(db.String(60), default="")
    purchase_price = db.Column(db.Float, default=0.0)
    selling_price = db.Column(db.Float, default=0.0)
    quantity_available = db.Column(db.Integer, default=0)
    low_stock_threshold = db.Column(db.Integer, default=5)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoice_items = db.relationship("InvoiceItem", backref="product", lazy=True)

    def quantity_sold(self):
        return sum(item.quantity for item in self.invoice_items if item.invoice.status != "draft")

    def revenue(self):
        return round(sum(item.line_total for item in self.invoice_items if item.invoice.status != "draft"), 2)

    def cost_of_goods_sold(self):
        return round(self.quantity_sold() * self.purchase_price, 2)

    def profit(self):
        return round(self.revenue() - self.cost_of_goods_sold(), 2)

    def is_low_stock(self):
        return self.quantity_available <= self.low_stock_threshold


class Client(db.Model):
    __tablename__ = "clients"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    name = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(30), default="")
    email = db.Column(db.String(120), default="")
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    invoices = db.relationship("Invoice", backref="client", lazy=True, cascade="all, delete-orphan",
                                order_by="Invoice.created_at.desc()")

    def total_billed(self):
        return round(sum(i.total_amount for i in self.invoices if i.status != "draft"), 2)

    def total_paid(self):
        return round(sum(i.amount_paid for i in self.invoices if i.status != "draft"), 2)

    def total_pending(self):
        return round(max(self.total_billed() - self.total_paid(), 0), 2)


class Invoice(db.Model):
    __tablename__ = "invoices"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    client_id = db.Column(db.Integer, db.ForeignKey("clients.id"), nullable=False)

    invoice_number = db.Column(db.String(30), unique=True, nullable=False)
    issue_date = db.Column(db.Date, default=date.today)
    due_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(20), default="unpaid")  # draft, unpaid, paid, overdue, cancelled

    subtotal = db.Column(db.Float, default=0.0)
    discount_percent = db.Column(db.Float, default=0.0)
    discount_amount = db.Column(db.Float, default=0.0)
    gst_percent = db.Column(db.Float, default=0.0)
    gst_amount = db.Column(db.Float, default=0.0)
    total_amount = db.Column(db.Float, default=0.0)
    amount_paid = db.Column(db.Float, default=0.0)

    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    items = db.relationship("InvoiceItem", backref="invoice", lazy=True, cascade="all, delete-orphan")

    def balance_due(self):
        return round(max(self.total_amount - self.amount_paid, 0), 2)


class InvoiceItem(db.Model):
    __tablename__ = "invoice_items"

    id = db.Column(db.Integer, primary_key=True)
    invoice_id = db.Column(db.Integer, db.ForeignKey("invoices.id"), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey("products.id"), nullable=True)

    description = db.Column(db.String(200), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Float, default=0.0)
    line_total = db.Column(db.Float, default=0.0)


class ImportBatch(db.Model):
    __tablename__ = "import_batches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    filename = db.Column(db.String(255), default="")
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    row_count = db.Column(db.Integer, default=0)       # rows found in the file
    imported_count = db.Column(db.Integer, default=0)   # rows actually committed as expenses
    skipped_count = db.Column(db.Integer, default=0)     # rows that failed validation

    expenses = db.relationship("Expense", backref="import_batch", lazy=True)

    def total_amount(self):
        return round(sum(e.amount for e in self.expenses), 2)

    def date_range(self):
        dates = [e.date for e in self.expenses]
        return (min(dates), max(dates)) if dates else (None, None)


class FilingProject(db.Model):
    """A user's request for help with IT (Income Tax) filing, open for auditors to bid on."""
    __tablename__ = "filing_projects"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.Text, default="")
    period_start = db.Column(db.Date, nullable=False)
    period_end = db.Column(db.Date, nullable=False)
    bid_deadline = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), default="open")  # open, awarded, completed, cancelled
    platform_fee_percent = db.Column(db.Float, default=10.0)
    winning_bid_id = db.Column(db.Integer, nullable=True)  # not a DB-level FK — see note below
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    bids = db.relationship("Bid", backref="project", lazy=True,
                            cascade="all, delete-orphan", foreign_keys="Bid.filing_project_id")
    # winning_bid_id intentionally has no db.ForeignKey(): Bid.filing_project_id -> filing_projects.id
    # and FilingProject.winning_bid_id -> bids.id would form a circular FK dependency between the two
    # tables that SQLite/SQLAlchemy can't reliably order table creation for. The relationship below
    # still works at the ORM level via an explicit join condition.
    winning_bid = db.relationship(
        "Bid", primaryjoin="foreign(FilingProject.winning_bid_id) == Bid.id", uselist=False, viewonly=True,
    )

    def lowest_bid(self):
        active = [b for b in self.bids if b.status in ("pending", "won")]
        return min(active, key=lambda b: b.amount) if active else None

    def bid_deadline_passed(self):
        return date.today() > self.bid_deadline


class Bid(db.Model):
    """An auditor's quoted fee to handle a given FilingProject."""
    __tablename__ = "bids"

    id = db.Column(db.Integer, primary_key=True)
    filing_project_id = db.Column(db.Integer, db.ForeignKey("filing_projects.id"), nullable=False)
    auditor_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)

    amount = db.Column(db.Float, nullable=False)
    message = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="pending")  # pending, won, lost, withdrawn
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    auditor = db.relationship("User", foreign_keys=[auditor_id], backref="bids_made")

    def platform_commission(self):
        return round(self.amount * (self.project.platform_fee_percent / 100), 2)

    def auditor_payout(self):
        return round(self.amount - self.platform_commission(), 2)


class ContactMessage(db.Model):
    __tablename__ = "contact_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # null if sent while logged out

    name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(255), nullable=False)
    phone = db.Column(db.String(30), default="")
    message = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class ChatMessage(db.Model):
    __tablename__ = "chat_messages"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    role = db.Column(db.String(10), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


DEFAULT_CATEGORIES = [
    {"name": "Food",          "icon": "utensils",   "color": "#B57EDC"},
    {"name": "Travel",        "icon": "plane",      "color": "#8E6FCE"},
    {"name": "Shopping",      "icon": "bag",        "color": "#A783E1"},
    {"name": "Entertainment", "icon": "film",       "color": "#C79BEF"},
    {"name": "Fuel",          "icon": "fuel",       "color": "#9A7FE0"},
    {"name": "Education",     "icon": "book",       "color": "#7C5CBF"},
    {"name": "Medical",       "icon": "cross",      "color": "#B08DE8"},
    {"name": "Bills",         "icon": "receipt",    "color": "#976FDB"},
    {"name": "EMI",           "icon": "calendar",   "color": "#856AC9"},
    {"name": "Others",        "icon": "dots",       "color": "#D0B6F5"},
]
