import os

#Importing packages
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Declare variable
stock = {}
quantity= 0
balance = 0


# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    user = db.execute("SELECT * FROM users WHERE id = ?", session["user_id"])
    cash = user[0]["cash"]
    username = user[0]["username"]

    ##get data from transactions table
    summary = db.execute("SELECT stock, sum(quantity) as sum FROM (SELECT * FROM transactions WHERE user_id = ?) GROUP BY stock HAVING sum > 0", session["user_id"])
    all = 0
    for item in summary:
        item["name"] = lookup(item["stock"])["name"]
        item["price"] = lookup(item["stock"])["price"]
        item["total"] = item["sum"] * item["price"]
        all = all + item["total"]

    total = all + cash

    # Convert to USD format
    for item in summary:
        item["price"] = usd(item["price"])
        item["total"] = usd(item["total"])



    return render_template("home.html", cash = usd(cash), username = "Welcome, " + username, summary=summary, total= usd(total))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        global quantity, stock,  balance
        stock = lookup(request.form.get("symbol"))
        quantity = request.form.get("shares")
        price = stock["price"]
        total = int(quantity) * price

        #Get cash data
        user_id = session["user_id"]
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id )
        cash = user[0]["cash"]

        balance = cash - total
        return render_template("preview.html", stock = stock , quantity=quantity, total = usd(total), cash= usd(cash), balance = usd(balance), type="BUY")

    return render_template("buy.html")

@app.route("/confirm", methods=["POST"])
@login_required
def confirmed():

    user_id = session["user_id"]
    db.execute("UPDATE users SET cash = ? WHERE id = ?", balance, user_id)
    db.execute("INSERT INTO transactions (user_id, stock, price, quantity, time) VALUES (?,?,?,?, datetime('now','localtime'))", user_id, stock["symbol"], stock["price"], quantity )


    return redirect("/")



@app.route("/history")
@login_required
def history():
    """Show history of transactions"""

    transactions = db.execute("SELECT * FROM transactions WHERE user_id = ? ORDER BY time DESC", session["user_id"] )

    for trans in transactions:
        if trans["stock"] == "CASH":
            trans["type"] = "DEPOSIT"

        elif trans["quantity"] > 0:
            trans["type"] = "BUY"
        else:
            trans["type"] = "SELL"

        trans["quantity"] = abs(trans["quantity"])


    # print(transactions)


    return render_template("history.html", transactions = transactions)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?", request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]



        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    stock_info = {"name": "Netflix", "symbol": "NFLX", "price": 234 }

    if request.method == "POST":
        symbol = request.form.get("symbol")
        stock_info = lookup(symbol)
        return render_template("quote.html", stock_info = stock_info)




    return render_template("quote.html", stock_info = {})


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""


    if request.method == "POST":
        username = request.form.get("username")
        password = generate_password_hash(request.form.get("password"))
        confirmation = request.form.get("confirmation")

        db_usernames = db.execute("SELECT username from users") #this will return a list of dict
        usernames = [i["username"] for i in db_usernames] #this line is used to convert list of dict into list of values



        if not username or not password:
            return apology("Please enter username and password")


        if request.form.get("password") != confirmation:
            return apology("Password does not match")


        if username in usernames:
            return apology("Username already exists")



        else:


            db.execute("INSERT INTO users (username, hash) VALUES (?,?)", username, password)
            rows = db.execute("SELECT * FROM users WHERE username = ?", username)
            session["user_id"] = rows[0]["id"]
            flash(f'You have successfully registered ')

            return redirect("/")


    return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""

    options = db.execute("SELECT stock, sum(quantity) as sum FROM transactions WHERE user_id = ? GROUP BY stock HAVING sum > 0", session["user_id"])
    print(options)

    if request.method == "POST":
        global quantity, stock,  balance
        stock = lookup(request.form.get("symbol"))
        quantity = int(request.form.get("shares")) * -1
        price = stock["price"]
        total = quantity * price

        #Get cash data
        user_id = session["user_id"]
        user = db.execute("SELECT * FROM users WHERE id = ?", user_id )
        cash = user[0]["cash"]

        balance = cash - total
        return render_template("preview.html", stock = stock , quantity=abs(quantity), total = usd(abs(total)), cash= usd(cash), balance = usd(balance), type="SELL")

    return render_template("sell.html", options=options)


@app.route("/deposit", methods=["GET", "POST"])
@login_required
def deposit():
    if request.method == "POST":
        amount = request.form.get("amount")
        user_id = session["user_id"]

        db.execute("UPDATE users SET cash = cash + ? WHERE id = ?", amount, user_id)
        db.execute("INSERT INTO transactions (user_id, stock, price, quantity, time) VALUES (?, 'CASH', ?, 1, datetime('now','localtime'))", user_id, amount )
        flash(f'You have successfully deposit: ${amount} ')





    return render_template("addcash.html")


@app.route("/changepass", methods = ["POST", "GET"])
def changepass():
    if request.method == "POST":
        old = request.form.get("oldpass")
        new = request.form.get("newpass")
        confirm = request.form.get("confirm")
        user_id = session["user_id"]

        user = db.execute("SELECT hash FROM users WHERE id = ?" , user_id )
        if not check_password_hash(user[0]["hash"], old):
            return apology("Wrong Password")

        elif new != confirm:
            return apology("Password does not match")

        else:

            password = generate_password_hash(confirm)
            db.execute("UPDATE users SET hash = ? WHERE id = ?", password, user_id)
            flash('Your password has been updated')
            return redirect("/")




    return render_template("changepass.html")
