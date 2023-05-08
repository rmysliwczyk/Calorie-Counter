# TODO:
# Store information about current logged in user in a session token

from flask import *
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash
from datetime import date
from submodules import login_required
import sqlite3

app = Flask(__name__)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

con = sqlite3.connect("caloriecounter.db", check_same_thread=False)
cur = con.cursor()

@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        cur.execute("DELETE FROM meals WHERE id=?", (request.form.get("meal_to_delete"),))
        con.commit()
    session["calories_today"] = 0
    selected_date = request.args.get("selected_date")

    if not selected_date:
        selected_date = date.today()

    res = cur.execute("SELECT * FROM meals WHERE date=? AND username=?", (selected_date, session["user"]))
    res = res.fetchall()
    for result in res:

        if str(result[1]) == str(selected_date):
         session["calories_today"] = round(session["calories_today"] + result[5], 2)

    return render_template("index.htm", meals=res, calorie_total=session["calories_today"], selected_date=selected_date)

@app.route("/logout")
def logout():
    session["user"] = None
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.htm")
    
    username = request.form.get("username")
    password = request.form.get("password")
    if not username:
        return handle_error("Username can't be empty")

    username_from_db = cur.execute("SELECT username FROM users WHERE username = ?", (username,))
    username_from_db = username_from_db.fetchone()
    if not username_from_db:
        return handle_error("Username does not exist")
    
    if not password:
        return handle_error("Password can't be empty")

    password_hash = cur.execute("SELECT hash FROM users WHERE username = ?", (username,))
    password_hash = password_hash.fetchone()[0]

    if not check_password_hash(password_hash, password):
        return handle_error("Incorrect password")

    session["user"] = username
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.htm")
    
    username = request.form.get("username")
    password = request.form.get("password")
    if not username:
        return handle_error("Username can't be empty")

    if not cur.execute("SELECT username FROM users WHERE username = ?", (username,)):
        return handle_error("Username already exists")
    
    if not password:
        return handle_error("Password can't be empty")

    cur.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, generate_password_hash(password)))
    con.commit()
    return redirect("/login")


@app.route("/browsedatabase", methods=["GET", "POST"])
@login_required
def browsedatabase():
    if request.method == "POST":
        cur.execute("DELETE FROM products WHERE id=?",(request.form.get("product_to_delete"),))
        con.commit()

    res = cur.execute("SELECT * FROM products ORDER BY product_name ASC")
    res = res.fetchall()
    return render_template("browsedatabase.htm", products=res)

@app.route("/addmeal", methods=["GET", "POST"])
@login_required
def addmeal():
    if request.method == "GET":
        product_name = request.args.get("product")
        barcode = session.get("barcode")
        session["barcode"] = None
        if barcode:
            res = cur.execute("SELECT * FROM products WHERE barcode=?", (barcode,))
            res = res.fetchone()
            return render_template("addmeal.htm", selected_product=res, todays_date = date.today())
        elif not product_name:
            res = cur.execute("SELECT * FROM products")
            res = res.fetchall()
            return render_template("addmeal.htm", products=res)
        else:
            product_name = product_name.strip()
            res = cur.execute("SELECT * FROM products WHERE product_name=?", (product_name,))
            res = res.fetchone()
            return render_template("addmeal.htm", selected_product=res, todays_date = date.today())
    else:
        meal_date = request.form.get("date")
        if not meal_date:
            meal_date = date.today()
        product_name = request.form.get("product_name")
        meal_weight = request.form.get("weight")
        print(product_name)
        if not product_name or not meal_date or not meal_weight:
            return handle_error("Missing required fields")
        else:

            res = cur.execute("SELECT * FROM products WHERE product_name=?", (product_name,))
            res = res.fetchone()
            session["new_meal_calories"] = round(float(res[2]/100.0) * float(meal_weight), 2)

            cur.execute("INSERT INTO meals (date, username, product_name, weight, calories) VALUES (?,?,?,?,?)", (meal_date, session["user"], product_name, meal_weight, session["new_meal_calories"]))
            con.commit()
            return redirect("/")


@app.route("/addproduct", methods=["GET", "POST"])
@login_required
def addproduct():
    if request.method == "GET":
        barcode = session.get("barcode")
        session["barcode"] = None
        return render_template("addproduct.htm", barcode=barcode)
    else:
        product_name = request.form.get("product_name").strip()
        calories = request.form.get("calories")
        fats = request.form.get("fats")
        carbohydrates = request.form.get("carbohydrates")
        proteins = request.form.get("proteins")
        portion_size = request.form.get("portion_size")
        barcode_post = request.form.get("barcode")

        if not product_name or not calories or not  proteins or not fats or not carbohydrates:
            return handle_error("Missing required fields")
        elif (float(fats) < 0 or float(carbohydrates) < 0 or float(proteins) < 0 or float(calories) < 0):
            return handle_error("Value cannot be less than zero")
        else:
            cur.execute(
            "INSERT INTO products (product_name, calories, fats, carbohydrates, proteins, portion_size, barcode) VALUES (?,?,?,?,?,?,?) ",
            (product_name, calories, fats, carbohydrates, proteins, portion_size, barcode_post))
            con.commit()
            return render_template("addproduct.htm")
        
        return handle_error("Couldn't add product to database")

@app.route("/scanbarcode", methods=["GET", "POST"])
@login_required
def scanbarcode():
    if request.method == "POST":
        session["barcode"] = request.form.get("barcode")
        if request.form.get("barcode_request_origin") == "addproduct":
            return redirect("/addproduct")
        elif request.form.get("barcode_request_origin") == "addmeal":
            return redirect("/addmeal")
    return render_template("scanbarcode.htm", barcode_request_origin=request.args.get("barcode_request_origin"))


def handle_error(error_message):
    print(error_message)
    return redirect("/")

if __name__ == ("__main__"):
    app.run()
