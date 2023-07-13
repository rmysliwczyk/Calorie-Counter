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
con.execute("PRAGMA foreign_keys = ON")

def calculate_calories(selected_date):
    session["calories_today"] = 0
    if not selected_date:
        selected_date = date.today()

    with con:
        res = con.execute("SELECT * FROM meals WHERE date=? AND username=?", (selected_date, session["user"]))
        res = res.fetchall()
    for result in res:

        if str(result[1]) == str(selected_date):
         session["calories_today"] = round(session["calories_today"] + result[5], 2)


@app.route("/", methods=["GET", "POST"])
@login_required
def index():
    if request.method == "POST":
        with con:
            con.execute("DELETE FROM meals WHERE id=?", (request.form.get("meal_to_delete"),))
    selected_date = request.args.get("selected_date")
    if not selected_date:
        selected_date = date.today()

    calculate_calories(selected_date)
    with con:
        res = con.execute("SELECT * FROM meals WHERE date=? AND username=?", (selected_date, session["user"]))
        res = res.fetchall()

    #First item of the inner list element represents the meal time, second one, total calories for the meal time.
    meal_times = [
        {"meal_time_name":"Breakfast", "meal_time_calories":0}, 
        {"meal_time_name":"Lunch", "meal_time_calories":0},
        {"meal_time_name":"Dinner", "meal_time_calories":0}
        ]

    meal_time_exists = False
    for meal in res:
        for meal_time in meal_times:
            if meal[6] == meal_time["meal_time_name"]:
                meal_time_exists = True
        if meal_time_exists == False:                 
            meal_times.append({"meal_time_name":meal[6], "meal_time_calories": 0})
    
    for meal in res:
        for meal_time in meal_times:
            if meal[6] == meal_time["meal_time_name"]:
                meal_time["meal_time_calories"] = round(meal_time["meal_time_calories"] + meal[5], 2)

    return render_template("index.htm", meals=res, calorie_total=session["calories_today"], selected_date=selected_date, meal_times=meal_times)


@app.route("/logout")
def logout():
    session["user"] = None
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.htm")
    
    username = request.form.get("username")
    password = request.form.get("password")
    if not username:
        return handle_error("Username can't be empty")

    with con:
        username_from_db = con.execute("SELECT username FROM users WHERE username = ?", (username,))
        username_from_db = username_from_db.fetchone()
    if not username_from_db:
        return handle_error("Username does not exist")
    
    if not password:
        return handle_error("Password can't be empty")

    with con:
        password_hash = con.execute("SELECT hash FROM users WHERE username = ?", (username,))
        password_hash = password_hash.fetchone()[0]

    if not check_password_hash(password_hash, password):
        return handle_error("Incorrect password")

    session["user"] = username
    return redirect(url_for("index"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "GET":
        return render_template("register.htm")
    
    username = request.form.get("username")
    password = request.form.get("password")
    if not username:
        return handle_error("Username can't be empty")

    with con:
        if not con.execute("SELECT username FROM users WHERE username = ?", (username,)):
            return handle_error("Username already exists")
    
    if not password:
        return handle_error("Password can't be empty")

    with con:
        con.execute("INSERT INTO users (username, hash) VALUES (?, ?)", (username, generate_password_hash(password)))

    return redirect(url_for("login"))


@app.route("/browsedatabase", methods=["GET", "POST"])
@login_required
def browsedatabase():
    if request.method == "POST":
        with con:
            con.execute("DELETE FROM products WHERE id=?",(request.form.get("product_to_delete"),))

    search_string = request.args.get("search_field")
    if not search_string:
        search_string = ""

    with con:
        res = con.execute("SELECT * FROM products WHERE product_name LIKE ? ORDER BY product_name ASC", ("%" + search_string + "%",))
        res = res.fetchall()
    return render_template("browsedatabase.htm", products=res)


@app.route("/addmeal", methods=["GET", "POST"])
@login_required
def addmeal():
    calculate_calories(date.today())
    if request.method == "GET":
        if request.args.get("meal_time"):
            session["which_meal_time_to_add"] = request.args.get("meal_time")

        product_name = request.args.get("product")
        barcode = session.get("barcode")
        session["barcode"] = None
        product_from_list = request.args.get("product_from_list")

        if product_from_list:
            with con:
                res = con.execute("SELECT * FROM products WHERE id = ?", (product_from_list,))
                res = res.fetchone()
            return render_template("addmeal.htm", selected_product=res, todays_date=date.today(), calories_today=session["calories_today"], meal_time=session["which_meal_time_to_add"])

        if barcode:
            with con:
                res = con.execute("SELECT * FROM products WHERE barcode=?", (barcode,))
                res = res.fetchone()
            if res is None:
                # Product not found in database
                return redirect(url_for("addproduct", message="Product not found"))
            return render_template("addmeal.htm", selected_product=res, todays_date = date.today(), calories_today=session["calories_today"], meal_time=session["which_meal_time_to_add"])
        elif product_name:
            product_name = product_name.strip()
            with con:
                res = con.execute("SELECT * FROM products WHERE product_name LIKE ? ORDER BY product_name ASC", ("%" + product_name + "%",))
                res = res.fetchall()
            return render_template("addmeal.htm", product_list=res, todays_date=date.today(), calories_today=session["calories_today"], meal_time=session["which_meal_time_to_add"], entered_string=product_name)
        else:
            return render_template("addmeal.htm", todays_date=date.today(), calories_today=session["calories_today"], meal_time=session["which_meal_time_to_add"])
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
            with con:
                res = con.execute("SELECT * FROM products WHERE product_name=?", (product_name,))
                res = res.fetchone()
            session["new_meal_calories"] = round(float(res[2]/100.0) * float(meal_weight), 2)

            with con:
                con.execute("INSERT INTO meals (date, username, product_name, weight, calories, meal_time) VALUES (?,?,?,?,?,?)", (meal_date, session["user"], product_name, meal_weight, session["new_meal_calories"], session["which_meal_time_to_add"]))

            return redirect(url_for("index"))

@app.route("/addingredient", methods=["GET", "POST"])
@login_required
def addingredient():
    calculate_calories(date.today())
    if request.method == "GET":

        product_name = request.args.get("product")
        barcode = session.get("barcode")
        session["barcode"] = None
        product_from_list = request.args.get("product_from_list")

        if product_from_list:
            with con:
                res = con.execute("SELECT * FROM products WHERE id = ?", (product_from_list,))
                res = res.fetchone()
            return render_template("addingredient.htm", selected_product=res, calories_today=session["calories_today"])

        if barcode:
            with con:
                res = con.execute("SELECT * FROM products WHERE barcode=?", (barcode,))
                res = res.fetchone()
            if res is None:
                # Product not found in database
                return redirect(url_for("addproduct", message="Product not found"))
            return render_template("addingredient.htm", selected_product=res, calories_today=session["calories_today"])
        elif product_name:
            product_name = product_name.strip()
            with con:
                res = con.execute("SELECT * FROM products WHERE product_name LIKE ? ORDER BY product_name ASC", ("%" + product_name + "%",))
                res = res.fetchall()
            return render_template("addingredient.htm", product_list=res, calories_today=session["calories_today"], entered_string=product_name)
        else:
            return render_template("addingredient.htm", calories_today=session["calories_today"])
    else:
        product_name = request.form.get("product_name")
        meal_weight = request.form.get("weight")
        if not product_name or not meal_weight:
            return handle_error("Missing required fields")
        else:
            with con:
                res = con.execute("SELECT * FROM products WHERE product_name=?", (product_name,))
                res = res.fetchone()
            if not session.get("ingredients"):
                session["ingredients"] = []
            session["ingredients"].append({res[0]:{"calories": round(float(res[2]/100.0) * float(meal_weight), 2), "weight": meal_weight}})

            return redirect(url_for("addrecipe"))

@app.route("/addrecipe", methods=["GET", "POST"])
@login_required
def addrecipe():
    ingredients = []
    with con:
        if session.get("ingredients"):
            for ingredient in session["ingredients"]:
                for k, v in ingredient.items():
                    res = con.execute("SELECT product_name FROM products WHERE id=?", (k,))
                    res = res.fetchone()
                    ingredients.append({"product_name": res[0], "weight": v["weight"], "calories": v["calories"]})
    print(ingredients)
    return render_template("addrecipe.htm", ingredients=ingredients)

@app.route("/addproduct", methods=["GET", "POST"])
@login_required
def addproduct():
    if request.method == "GET":
        barcode = session.get("barcode")
        message = request.args.get("message")
        session["barcode"] = None
        return render_template("addproduct.htm", barcode=barcode, message=message)
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
            with con:
                con.execute(
                "INSERT INTO products (product_name, calories, fats, carbohydrates, proteins, portion_size, barcode) VALUES (?,?,?,?,?,?,?) ",
                (product_name, calories, fats, carbohydrates, proteins, portion_size, barcode_post))
            return render_template("addproduct.htm")
        
        return handle_error("Couldn't add product to database")


@app.route("/scanbarcode", methods=["GET", "POST"])
@login_required
def scanbarcode():
    if request.method == "POST":
        session["barcode"] = request.form.get("barcode")
        if request.form.get("barcode_request_origin") == "addproduct":
            return redirect(url_for("addproduct"))
        elif request.form.get("barcode_request_origin") == "addmeal":
            return redirect(url_for("addmeal"))
        elif request.form.get("barcode_request_origin") == "addingredient":
            return redirect(url_for("addingredient"))
    return render_template("scanbarcode.htm", barcode_request_origin=request.args.get("barcode_request_origin"))


def handle_error(error_message):
    print(error_message)
    return redirect(url_for("index"))


if __name__ == ("__main__"):
    app.run()
