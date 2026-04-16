# pyre-ignore-all-errors
import os
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from collections import Counter
from werkzeug.utils import secure_filename
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
from datetime import datetime
import razorpay

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "aroma-essence-dev-key-2026")

@app.template_filter('datetimeformat')
def datetimeformat(value):
    if value:
        return value.strftime('%d %b %Y, %I:%M %p')
    return ""

# ------------------- DATABASE SETUP -------------------
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///perfume.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

client = razorpay.Client(auth=("rzp_test_SZ6IDjdDLrKTl8", "BjkAPhzrjWbJc6t8egbXvjvy"))

UPLOAD_FOLDER = 'static/images'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# ------------------- DATABASE MODELS -------------------
class Product(db.Model):
    id          = db.Column(db.Integer, primary_key=True)
    name        = db.Column(db.String(100), nullable=False)
    price       = db.Column(db.Float, nullable=False)
    description = db.Column(db.Text)
    image       = db.Column(db.String(200))
    # Rich attributes for recommendation engine
    category    = db.Column(db.String(50), default='Floral')       # Floral, Woody, Fresh, Oriental, Citrus
    scent_notes = db.Column(db.String(300), default='')            # e.g. "rose jasmine musk"
    gender      = db.Column(db.String(20), default='Unisex')       # Men, Women, Unisex
    occasion    = db.Column(db.String(100), default='Everyday')    # Everyday, Evening, Office, Party
    season      = db.Column(db.String(100), default='All Seasons') # Summer, Winter, Spring, Autumn

class User(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    name       = db.Column(db.String(100))
    email      = db.Column(db.String(100), unique=True)
    password   = db.Column(db.String(200))
    is_admin   = db.Column(db.Boolean, default=False)
    cart_items = db.relationship('CartItem', backref='user', lazy=True)
    views      = db.relationship('UserView', backref='user', lazy=True)

class ContactMessage(db.Model):
    id      = db.Column(db.Integer, primary_key=True)
    name    = db.Column(db.String(100))
    email   = db.Column(db.String(100))
    message = db.Column(db.Text)

class CartItem(db.Model):
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    quantity   = db.Column(db.Integer, default=1)
    product    = db.relationship('Product')

class UserView(db.Model):
    """Tracks which products a user has viewed, for personalised recommendations."""
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('product.id'), nullable=False)
    product    = db.relationship('Product')

class Order(db.Model):
    """Tracks completed orders — used to check if a user is a first-time buyer."""
    id           = db.Column(db.Integer, primary_key=True)
    user_id      = db.Column(db.Integer, db.ForeignKey('user.id'))
    product_name = db.Column(db.String(200))
    total_price  = db.Column(db.Float)
    quantity     = db.Column(db.Integer)
    address      = db.Column(db.String(300))
    status       = db.Column(db.String(50), default="Pending")
    date         = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')

# ------------------- INITIAL DATA -------------------
with app.app_context():
    db.drop_all()
    db.create_all()
    if True:
        sample_products = [
            Product(
                name="Rose Elegance", price=1999,
                description="A timeless floral elegance, opening with fresh rose petals and settling into warm musk and soft sandalwood.",
                image="rose.jpg",
                category="Floral", gender="Women", occasion="Evening, Party",
                season="Spring, Summer",
                scent_notes="rose petals jasmine musk sandalwood powder"
            ),
            Product(
                name="Ocean Breeze", price=2499,
                description="Dive into freshness with this crisp aquatic fragrance, blending sea salt, driftwood and a hint of citrus.",
                image="ocean.jpg",
                category="Fresh", gender="Men", occasion="Everyday, Office",
                season="Summer, Spring",
                scent_notes="sea salt aquatic driftwood citrus bergamot clean"
            ),
            Product(
                name="Vanilla Dream", price=1799,
                description="A warm, gourmand embrace of sweet vanilla, caramel, and soft white musk for a cozy comforting feel.",
                image="vanilla.jpg",
                category="Oriental", gender="Women", occasion="Everyday, Evening",
                season="Autumn, Winter",
                scent_notes="vanilla caramel sweet musk amber warm gourmand"
            ),
            Product(
                name="Jasmine Bliss", price=2199,
                description="An intoxicating bouquet of fresh jasmine intertwined with green tea and white cedar for ethereal brightness.",
                image="jasmine.jpg",
                category="Floral", gender="Women", occasion="Everyday, Office",
                season="Spring, Summer",
                scent_notes="jasmine green tea white cedar floral petals light"
            ),
            Product(
                name="Lavender Calm", price=1899,
                description="A soothing aromatherapy-inspired blend of lavender, chamomile, and soft oak moss for tranquil moments.",
                image="lavender.jpg",
                category="Fresh", gender="Unisex", occasion="Everyday",
                season="All Seasons",
                scent_notes="lavender chamomile oak moss herbal green soothing"
            ),
            Product(
                name="Sandalwood Secret", price=2599,
                description="Deep, smoky, and sensual — a rich foundation of Indian sandalwood, resin, and vetiver with spicy top notes.",
                image="sandalwood.jpg",
                category="Woody", gender="Men", occasion="Evening, Party",
                season="Autumn, Winter",
                scent_notes="sandalwood vetiver resin spice smoke oud cedar woody"
            ),
            Product(
                name="Citrus Sunrise", price=1999,
                description="Start your day with a burst of energy — sparkling lemon, grapefruit and orange zest over a clean white musk base.",
                image="citrus.jpg",
                category="Citrus", gender="Unisex", occasion="Everyday, Office",
                season="Summer, Spring",
                scent_notes="lemon grapefruit orange zest bergamot citrus fresh musk"
            ),
            Product(
                name="Musk Harmony", price=2699,
                description="A sophisticated blend of warm musk, amber, and subtle spice that creates an irresistible, skin-close fragrance.",
                image="musk.jpg",
                category="Oriental", gender="Unisex", occasion="Evening, Party",
                season="Autumn, Winter",
                scent_notes="musk amber spice warm skin iris powder sensual"
            ),
            Product(
                name="Amber Mystique", price=2799,
                description="A rich, opulent tapestry of golden amber, dark resins, patchouli, and vanilla for an unforgettable presence.",
                image="amber.jpg",
                category="Oriental", gender="Women", occasion="Evening, Party",
                season="Autumn, Winter",
                scent_notes="amber resin patchouli vanilla dark oud balsamic opulent"
            ),
            Product(
                name="Berry Delight", price=2099,
                description="Playful and vibrant — a fruity burst of raspberry, blackcurrant, and peach over soft floral and musk.",
                image="berry.jpg",
                category="Floral", gender="Women", occasion="Everyday, Party",
                season="Spring, Summer",
                scent_notes="raspberry blackcurrant peach berry fruity floral musk light"
            ),
            Product(
                name="Royal Oud Attar", price=3499,
                description="An authentic, concentrated traditional Indian attar blending rich oudh, rose, and amber without alcohol.",
                image="attar_oud.png",
                category="Attar", gender="Unisex", occasion="Evening, Party",
                season="Winter, Autumn",
                scent_notes="oudh rose amber saffron musk traditional concentrated"
            ),
            Product(
                name="Musk Amber Attar",
                price=2800,
                description="Warm amber blended with sensual musk.",
                image="MuskAmberAttar.jpg",
                category="Attar",
                gender="Unisex",
                occasion="Party",
                season="Winter",
                scent_notes="musk amber warm sweet"
            ),
            Product(
                name="Rose Attar Classic",
                price=2500,
                description="Traditional rose attar from Kannauj.",
                image="RoseAttarClassic.jpg",
                category="Attar",
                gender="Women",
                occasion="Daily",
                season="Spring",
                scent_notes="rose floral sweet fresh"
            ),
            Product(
                name="Sandalwood Attar",
                price=3000,
                description="Pure sandalwood oil with calming aroma.",
                image="SandalwoodAttar.jpg",
                category="Attar",
                gender="Unisex",
                occasion="Meditation",
                season="All Seasons",
                scent_notes="sandalwood creamy woody soft"
            ),
            Product(
                name="Lavender Room Freshener", price=1299,
                description="Transform your home into a tranquil spa with this premium room spray and fabric freshener.",
                image="home_freshener.png",
                category="Home Fragrance", gender="Unisex", occasion="Everyday",
                season="All Seasons",
                scent_notes="lavender chamomile fresh linen clean home freshener"
            ),
            Product(
                name="Luxury Discovery Box", price=4999,
                description="The ultimate gifting experience. A curated collection of our finest miniature perfumes in a velvet-lined box.",
                image="gift_set.png",
                category="Gifting", gender="Unisex", occasion="Gift",
                season="All Seasons",
                scent_notes="floral woody amber citrus variety gift set presentation"
            ),
                Product(
                name="Romantic Gift Set",
                price=3000,
                description="Perfect romantic fragrance combo for special moments.",
                image="RomanticGiftSet.jpg",
                category="Gifting",
                gender="Women",
                occasion="Valentine",
                season="Winter",
                scent_notes="rose vanilla sweet romantic"
           ),
                Product(
                name="Men’s Executive Gift Kit",
                price=3999,
                description="Elegant fragrance kit for modern men.",
                image="Men’sExecutiveGiftKit.jpg",
                category="Gifting",
                gender="Men",
                occasion="Corporate",
                season="All Seasons",
                scent_notes="woody musk strong bold"
        ),
            Product(
                name="Aqua Sunshine", price=2199,
                description="The ultimate summer escape. Bright citrus notes layered over a marine accord for hot, sunny days.",
                image="summer_perfume.png",
                category="Fresh", gender="Unisex", occasion="Everyday, Holiday",
                season="Summer",
                scent_notes="citrus marine aquatic bright sun beach fresh warm summer"
            ),
            Product(name="Mediterranean Citrus", price=2100, description="A vibrant splash of Italian lemons, bergamot, and a refreshing sea breeze.", image="citrus.jpg", category="Citrus", gender="Unisex", occasion="Everyday", season="Summer", scent_notes="lemon bergamot orange sea breeze fresh"),
            Product(name="Crystal Waters", price=2500, description="Cool, clear, and aquatic. Notes of sea salt, marine accord, and water lily.", image="ocean.jpg", category="Aquatic", gender="Unisex", occasion="Everyday", season="Summer", scent_notes="sea salt marine water lily cool aquatic"),
            Product(name="Bergamot & Basil", price=1950, description="An incredibly crisp and green scent featuring sharp bergamot and crushed basil leaves.", image="citrus.jpg", category="Fresh", gender="Unisex", occasion="Office, Everyday", season="Summer", scent_notes="bergamot basil green leaves crisp tart"),
            Product(name="Sorrento Lemon", price=1800, description="Pure sunshine in a bottle with Sicilian lemon, sparkling mandarin, and soft neroli.", image="citrus.jpg", category="Citrus", gender="Unisex", occasion="Everyday", season="Summer", scent_notes="sicilian lemon mandarin neroli bright"),
            Product(name="Lotus Pond", price=2300, description="A delicate, watery floral featuring blooming lotus, water lily, and a hint of green tea.", image="jasmine.jpg", category="Light Floral", gender="Women", occasion="Everyday", season="Summer", scent_notes="lotus water lily green tea delicate watery"),
            Product(name="Coastal Morning", price=2200, description="The scent of an early morning walk on the beach. Ocean mist, cucumber, and aloe.", image="ocean.jpg", category="Aquatic", gender="Unisex", occasion="Everyday", season="Summer", scent_notes="ocean mist cucumber aloe wet green"),
            Product(name="White Linen", price=2400, description="Airy and profoundly clean, evoking the scent of sun-dried cotton and white flowers.", image="lavender.jpg", category="Fresh", gender="Unisex", occasion="Office, Everyday", season="Summer", scent_notes="clean cotton white flower airy breezy"),
            Product(name="Iced Grapefruit", price=2000, description="A frosty, invigorating cocktail of pink grapefruit and crushed mint leaves.", image="citrus.jpg", category="Citrus", gender="Unisex", occasion="Everyday, Party", season="Summer", scent_notes="pink grapefruit pink mint fizz sugar cold tart"),
            Product(name="Premium Gift Wrap", price=25, description="A luxurious satin ribbon wrapper and custom box.", image="gift_set.png", category="Extras", gender="Unisex", occasion="Gift", season="All Seasons", scent_notes="none"),
        ]
        db.session.add_all(sample_products)
        db.session.commit()

# ==================== RECOMMENDATION ENGINE ====================
def get_recommendations(product_id, n=4):
    """
    Content-based recommendation using TF-IDF + Cosine Similarity.
    Combines scent_notes, category, gender, occasion, and season
    into a single feature string per product for vectorisation.
    """
    products = Product.query.all()
    if len(products) <= 1:
        return []

    # Build a combined feature string for each product
    def build_features(p):
        return f"{p.scent_notes} {p.category} {p.gender} {p.occasion} {p.season}"

    product_ids    = [p.id for p in products]
    feature_corpus = [build_features(p) for p in products]

    # TF-IDF vectorization
    tfidf = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(feature_corpus)

    # Find index of requested product
    try:
        idx = product_ids.index(product_id)
    except ValueError:
        return []

    # Compute cosine similarity for this product against all others
    cosine_scores = cosine_similarity(tfidf_matrix[idx], tfidf_matrix).flatten()
    cosine_scores[idx] = -1  # exclude itself

    # Get top-n most similar indices
    top_indices = np.argsort(cosine_scores)[::-1][:n]
    return [products[i] for i in top_indices]


def get_personalized_recommendations(user_id, n=4):
    """
    Returns personalised recommendations for a logged-in user based on
    the last 5 products they viewed, using averaged TF-IDF vectors.
    """
    recent_views = (
        UserView.query
        .filter_by(user_id=user_id)
        .order_by(UserView.id.desc())
        .limit(5)
        .all()
    )
    if not recent_views:
        # Fall back to featured products
        return Product.query.limit(n).all()

    viewed_ids = [v.product_id for v in recent_views]

    products = Product.query.all()
    if len(products) <= 1:
        return []

    def build_features(p):
        return f"{p.scent_notes} {p.category} {p.gender} {p.occasion} {p.season}"

    product_ids    = [p.id for p in products]
    feature_corpus = [build_features(p) for p in products]

    tfidf        = TfidfVectorizer(stop_words='english')
    tfidf_matrix = tfidf.fit_transform(feature_corpus)

    # Average the TF-IDF vectors of all viewed products
    viewed_indices = [product_ids.index(vid) for vid in viewed_ids if vid in product_ids]
    if not viewed_indices:
        return Product.query.limit(n).all()

    avg_vector = np.mean(tfidf_matrix[viewed_indices].toarray(), axis=0, keepdims=True)
    cosine_scores = cosine_similarity(avg_vector, tfidf_matrix).flatten()

    # Exclude already-viewed products
    for vi in viewed_indices:
        cosine_scores[vi] = -1

    top_indices = np.argsort(cosine_scores)[::-1][:n]
    return [products[i] for i in top_indices]


# ==================== ROUTES ====================
@app.route('/')
def home():
    products = Product.query.limit(3).all()
    recommendations = []
    if 'user_id' in session:
        recommendations = get_personalized_recommendations(session['user_id'], n=4)
    return render_template("index.html", products=products, recommendations=recommendations)


@app.route('/shop')
def shop():
    category = request.args.get('category', '')
    gender   = request.args.get('gender', '')
    products = Product.query
    if category:
        products = products.filter(Product.category == category)
    if gender:
        products = products.filter(Product.gender == gender)
    products = products.all()
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories]
    return render_template("shop.html", products=products, categories=categories,
                           selected_category=category, selected_gender=gender)


@app.route('/product/<int:product_id>')
def product_detail(product_id):
    product = db.session.get(Product, product_id)
    if not product:
        flash("Product not found.", "error")
        return redirect(url_for('shop'))

    # Track user view for personalisation
    if 'user_id' in session:
        # Avoid duplicate consecutive views
        last_view = (
            UserView.query
            .filter_by(user_id=session['user_id'])
            .order_by(UserView.id.desc())
            .first()
        )
        if not last_view or last_view.product_id != product_id:
            db.session.add(UserView(user_id=session['user_id'], product_id=product_id))
            db.session.commit()

    recommendations = get_recommendations(product_id, n=4)
    return render_template("product_detail.html", product=product, recommendations=recommendations)


@app.route('/search')
def search():
    query    = request.args.get('q', '')
    products = Product.query.filter(
        Product.name.ilike(f'%{query}%') |
        Product.description.ilike(f'%{query}%') |
        Product.scent_notes.ilike(f'%{query}%') |
        Product.category.ilike(f'%{query}%')
    ).all()
    categories = db.session.query(Product.category).distinct().all()
    categories = [c[0] for c in categories]
    return render_template("shop.html", products=products, query=query, categories=categories)


@app.route('/reset-password', methods=['POST'])
def reset_password():
    email = request.form.get('email')
    user  = User.query.filter_by(email=email).first()
    if user:
        flash("Password reset instructions sent to your email.", "success")
    else:
        flash("Email not found!", "error")
    return redirect(url_for('home'))


@app.route('/about')
def about():
    return render_template("about.html")


@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        new_msg = ContactMessage(
            name=request.form['name'],
            email=request.form['email'],
            message=request.form['message']
        )
        db.session.add(new_msg)
        db.session.commit()
        flash("Message sent successfully!", "success")
        return redirect(url_for('contact'))
    return render_template("contact.html")


# ==================== AUTH ====================
@app.route('/signup', methods=['POST'])
def signup():
    name     = request.form['name']
    email    = request.form['email']
    password = generate_password_hash(request.form['password'])
    if User.query.filter_by(email=email).first():
        flash("Email already registered!", "error")
        return redirect(url_for('home'))
    user = User(name=name, email=email, password=password)
    db.session.add(user)
    db.session.commit()
    flash("Signup successful! Please log in.", "success")
    return redirect(url_for('home'))


@app.route('/login', methods=['POST'])
def login():
    email    = request.form['email']
    password = request.form['password']
    user     = User.query.filter_by(email=email).first()
    if user and check_password_hash(user.password, password):
        session['user_id']   = user.id
        session['user_name'] = user.name
        flash(f"Welcome back, {user.name}!", "success")
    else:
        flash("Invalid email or password.", "error")
    return redirect(url_for('home'))


@app.route('/logout')
def logout():
    session.clear()
    flash("Logged out successfully!", "success")
    return redirect(url_for('home'))


# ==================== CART ====================
@app.route('/add-to-cart', methods=['POST'])
def add_to_cart():
    if 'user_id' not in session:
        flash("Please log in to add items to cart.", "error")
        return redirect(url_for('home'))

    product_id = int(request.form['product_id'])
    user_id    = session['user_id']
    existing   = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if existing:
        existing.quantity += 1
    else:
        db.session.add(CartItem(user_id=user_id, product_id=product_id))
    db.session.commit()
    flash("Item added to cart!", "success")

    # Redirect back to product detail if we came from there
    next_url = request.form.get('next', url_for('shop'))
    return redirect(next_url)


@app.route('/cart')
def cart():
    if 'user_id' not in session:
        flash("Please login to view your cart.", "error")
        return redirect(url_for('home'))
    user_id    = session['user_id']
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    total      = sum(item.product.price * item.quantity for item in cart_items)
    return render_template("cart.html", cart_items=cart_items, total=total)


@app.route('/update-cart/<int:cart_id>', methods=['POST'])
def update_cart(cart_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    new_quantity = int(request.form.get('quantity', 1))
    cart_item    = db.session.get(CartItem, cart_id)
    if not cart_item:
        flash("Cart item not found.", "error")
        return redirect(url_for('cart'))
    if cart_item.user_id == session['user_id']:
        if new_quantity > 0:
            cart_item.quantity = new_quantity
            db.session.commit()
            flash("Quantity updated.", "success")
        else:
            db.session.delete(cart_item)
            db.session.commit()
            flash("Item removed.", "success")
    return redirect(url_for('cart'))


@app.route('/api/cart/drawer')
def api_cart_drawer():
    if 'user_id' not in session:
        return render_template('cart_drawer_content.html', cart_items=[], total=0, gift_wrap=None)
    user_id = session['user_id']
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    total = sum(item.product.price * item.quantity for item in cart_items)
    gift_wrap = Product.query.filter_by(name="Premium Gift Wrap").first()
    return render_template('cart_drawer_content.html', cart_items=cart_items, total=total, gift_wrap=gift_wrap)

@app.route('/api/cart/update', methods=['POST'])
def api_cart_update():
    if 'user_id' not in session:
        return {"error": "Not logged in"}, 401
    data = request.json
    cart_id = data.get('cart_id')
    new_quantity = int(data.get('quantity', 0))
    cart_item = db.session.get(CartItem, cart_id)
    if cart_item and cart_item.user_id == session['user_id']:
        if new_quantity > 0:
            cart_item.quantity = new_quantity
        else:
            db.session.delete(cart_item)
        db.session.commit()
    return {"message": "Success"}

@app.route('/api/cart/add', methods=['POST'])
def api_cart_add():
    if 'user_id' not in session:
        return {"error": "Not logged in"}, 401
    data = request.json
    product_id = int(data.get('product_id'))
    user_id = session['user_id']
    existing = CartItem.query.filter_by(user_id=user_id, product_id=product_id).first()
    if existing:
        existing.quantity += 1
    else:
        db.session.add(CartItem(user_id=user_id, product_id=product_id))
    db.session.commit()
    return {"message": "Success"}

@app.route('/remove-cart/<int:cart_id>')
def remove_cart(cart_id):
    if 'user_id' not in session:
        return redirect(url_for('home'))
    cart_item = db.session.get(CartItem, cart_id)
    if not cart_item:
        flash("Cart item not found.", "error")
        return redirect(url_for('cart'))
    if cart_item.user_id == session['user_id']:
        db.session.delete(cart_item)
        db.session.commit()
        flash("Item removed from cart.", "success")
    return redirect(url_for('cart'))


@app.route('/checkout', methods=['GET', 'POST'])
def checkout():
    if 'user_id' not in session:
        flash("Please login to checkout.", "error")
        return redirect(url_for('home'))
    user_id    = session['user_id']
    cart_items = CartItem.query.filter_by(user_id=user_id).all()
    total      = sum(item.product.price * item.quantity for item in cart_items)
    if request.method == 'POST':
        product_names = ", ".join([item.product.name for item in cart_items])
        total_quantity = sum(item.quantity for item in cart_items)
        address = request.form.get('address')
        new_order = Order(
            user_id=user_id,
            product_name=product_names,
            total_price=total,
            quantity=total_quantity,
            address=address
        )
        db.session.add(new_order)
        # clear cart
        db.session.query(CartItem).filter_by(user_id=user_id).delete()
        db.session.commit()
        flash("Order placed successfully! Thank you for shopping with Aroma Essence.", "success")
        return redirect(url_for('home'))
    return render_template("checkout.html", cart_items=cart_items, total=total)

@app.route('/api/apply-coupon', methods=['POST'])
def apply_coupon():
    if 'user_id' not in session:
        return {"error": "Please log in first."}, 401
    data = request.json
    code = (data.get('code') or '').strip().upper()
    user_id = session['user_id']

    if code == 'AROMA10':
        # Check if this user has placed an order before
        previous_orders = Order.query.filter_by(user_id=user_id).count()
        if previous_orders > 0:
            return {"error": "AROMA10 is valid for first-time orders only."}, 400
        cart_items = CartItem.query.filter_by(user_id=user_id).all()
        subtotal = sum(item.product.price * item.quantity for item in cart_items)
        discount = round(subtotal * 0.10, 2)
        new_total = round(subtotal - discount, 2)
        return {"success": True, "discount": discount, "new_total": new_total, "message": "10% discount applied!"}

    return {"error": "Invalid coupon code."}, 400


MOCK_BLOG_POSTS = [
    {
        "id": 1,
        "title": "How to Find Your Signature Scent",
        "category": "Fragrance Guide",
        "description": "Finding a signature scent is a personal journey. Learn the difference between top, heart, and base notes...",
        "content": "Finding a signature scent is a deeply personal journey. It goes beyond simply choosing a perfume that smells nice; it's about finding a fragrance that seamlessly blends with your body chemistry, complements your personality, and evokes the right emotions. <br><br> The key is understanding the fragrance pyramid. The \"top notes\" are the first impression, often citrus or light florals, which evaporate quickly. After 15-30 minutes, the \"heart notes\" (or middle notes) emerge, forming the core of the fragrance. Finally, the \"base notes\" settle in, providing depth and longevity with ingredients like woods, musk, and amber. <br><br> Experiment with different families—Floral, Oriental, Woody, and Fresh—to see what resonates with you. Remember to test on your skin, as fragrances evolve uniquely on everyone.",
        "image": "images/rose.jpg"
    },
    {
        "id": 2,
        "title": "The Ancient Art of Attar Making",
        "category": "Heritage",
        "description": "Discover the traditional degree and bhapka distillation process that dates back centuries in Kannauj...",
        "content": "Attar (or ittar) making is a magical, ancient process deeply rooted in tradition, particularly in the perfume capital of India, Kannauj. Unlike modern perfumes that rely heavily on alcohol bases and chemical synthesis, authentic attars are 100% natural, alcohol-free, and crafted through hydro-distillation. <br><br> The traditional \"Deg and Bhapka method\" uses a copper still (Deg) and a receiving vessel (Bhapka). Freshly plucked flowers like delicate roses or intoxicating jasmine are placed in water inside the Deg, which is sealed with clay. As it's heated over a wood fire, the steam carries the aromatic oils into the Bhapka, which sits in cold water to condense the vapor. The resulting oil often rests on a base of pure sandalwood oil, maturing for months or even years. <br><br> This time-honored craft creates fragrances so rich and complex, they are considered liquid gold.",
        "image": "images/attar_oud.png"
    },
    {
        "id": 3,
        "title": "Top 5 Summer Fragrances for 2026",
        "category": "Seasonal Picks",
        "description": "Beat the heat with our hand-picked selection of aquatic, citrus, and light floral perfumes perfect for sunny days.",
        "content": "When the temperature rises, heavy ouds and dense spices can feel overpowering. Summer calls for fragrances that refresh, invigorate, and energize. Here are our top picks for the 2026 summer season: <br><br> \"1. Aquatic Breeze:\" Imagine the scent of sea salt and coastal winds. Aquatic notes perfectly mimic a cool dip in the ocean. <br> \"2. Lemon Zest:\" Nothing cuts through humidity like sharp, sparkling citrus. Bergamot and Sicilian lemon are staples. <br> \"3. Green Tea & Lotus:\" For a serene, calming effect, green notes paired with watery florals offer a sophisticated chill. <br> \"4. White Linen:\" The scent of crisp, sun-dried cotton adds a clean, airy feel to your everyday routine. <br> \"5. Iced Grapefruit:\" A frosty cocktail of tart pink grapefruit and crushed mint to wake up your senses.",
        "image": "images/summer_perfume.png"
    }
]

@app.route('/blog')
def blog():
    return render_template('blog.html', posts=MOCK_BLOG_POSTS)

@app.route('/blog/<int:post_id>')
def blog_post(post_id):
    post = next((p for p in MOCK_BLOG_POSTS if p["id"] == post_id), None)
    if not post:
        flash("Blog post not found.", "error")
        return redirect(url_for('blog'))
    return render_template('blog_post.html', post=post)

@app.route('/summer-collection')
def summer_collection():
    # Strict summer constraint list
    valid_categories = ['Citrus', 'Aquatic', 'Fresh', 'Light Floral']
    heavy_notes = ['oud', 'leather', 'heavy amber', 'tobacco', 'warm spice', 'vanilla']
    
    # Pre-filter by categories from DB
    products = Product.query.filter(Product.category.in_(valid_categories)).all()
    
    # Python-level filter to explicitly exclude ANY heavy note profile
    summer_products = []
    for p in products:
        notes = p.scent_notes.lower() if p.scent_notes else ""
        if not any(heavy in notes for heavy in heavy_notes):
            summer_products.append(p)
            
    return render_template('shop.html', products=summer_products, category_title="Summer Collection")

@app.route('/rewards')
def rewards():
    return render_template('rewards.html')

@app.route('/reviews')
def reviews():
    return render_template('reviews.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect('/')

    user = User.query.get(session['user_id'])

    if not user:
        session.clear()
        return redirect('/')

    orders = Order.query.filter_by(user_id=user.id).all()

    total_orders = len(orders)
    total_spent = sum(o.total_price for o in orders)

    return render_template("profile.html", user=user, orders=orders, total_orders=total_orders, total_spent=total_spent)





@app.route('/admin/login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        if email == "sanketgurav28703@gmail.com" and password == "2003":
            session['admin'] = True
            return redirect('/admin')
        else:
            return render_template('admin_login.html', error="Invalid login")

    return render_template('admin_login.html')


@app.route('/admin')
def admin():
    if not session.get('admin'):
        return redirect('/admin/login')

    search = request.args.get('search', '')

    if search:
        products = Product.query.filter(
            Product.name.ilike(f'%{search}%')
        ).all()
    else:
        products = Product.query.all()

    users = User.query.all()

    total_products = Product.query.count()
    total_users = User.query.count()
    total_orders = Order.query.count()

    # Category data - SAFE VERSION
    products_all = Product.query.all()
    categories = [p.category if p.category else "Other" for p in products_all]
    category_count = dict(Counter(categories))

    return render_template('admin_dashboard.html', products=products, users=users,
        total_products=total_products, total_users=total_users, total_orders=total_orders,
        category_data=category_count)

@app.route('/admin/add', methods=['GET', 'POST'])
def add_product():
    if request.method == 'POST':

        file = request.files['image']
        filename = secure_filename(file.filename)
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        product = Product(
            name=request.form['name'],
            price=request.form['price'],
            image=filename,
            description=request.form['description'],
            category=request.form['category']
        )

        db.session.add(product)
        db.session.commit()

        return redirect('/admin')

    # ✅ THIS WAS MISSING
    return render_template('add.html')


@app.route('/admin/edit/<int:id>', methods=['GET', 'POST'])
def edit_product(id):
    product = Product.query.get(id)

    if request.method == 'POST':
        product.name = request.form['name']
        product.price = request.form['price']
        db.session.commit()
        return redirect('/admin')

    return render_template('edit.html', product=product)

@app.route('/admin/delete/<int:id>')
def delete_product(id):
    product = Product.query.get(id)
    db.session.delete(product)
    db.session.commit()
    return redirect('/admin')

@app.route('/admin/orders')
def admin_orders():
    if not session.get('admin'):
        return redirect('/admin/login')

    orders = Order.query.join(User).all()
    return render_template('admin_orders.html', orders=orders)



@app.route('/admin/order-status/<int:id>/<status>')
def update_order_status(id, status):
    order = Order.query.get(id)
    if order:
        order.status = status
        db.session.commit()
    return redirect('/admin/orders')

@app.route('/my-orders')
def my_orders():
    if 'user_id' not in session:
        return redirect('/')

    orders = Order.query.filter_by(user_id=session['user_id']).all()
    return render_template('my_orders.html', orders=orders)

@app.route('/address', methods=['GET', 'POST'])
def address():
    if 'user_id' not in session:
        return redirect('/')

    user = User.query.get(session['user_id'])

    if request.method == 'POST':
        user.address = request.form['address']
        db.session.commit()
        return redirect('/profile')

    return render_template("address.html", user=user)

@app.route('/track-order/<int:order_id>')
def track_order(order_id):
    if 'user_id' not in session:
        return redirect('/')

    order = Order.query.get(order_id)
    return render_template('track_order.html', order=order)

@app.route('/cancel-order/<int:order_id>')
def cancel_order(order_id):
    order = Order.query.get(order_id)

    if order and order.status == "Pending":
        order.status = "Rejected"
        db.session.commit()

    return redirect('/my-orders')

@app.route('/create-order', methods=['POST'])
def create_order():
    if 'user_id' not in session:
        return {"error": "Login required"}, 401

    user_id = session['user_id']
    cart_items = CartItem.query.filter_by(user_id=user_id).all()

    total = int(sum(item.product.price * item.quantity for item in cart_items) * 100)

    order_data = client.order.create({
        "amount": total,
        "currency": "INR",
        "payment_capture": 1
    })

    return {
        "id": order_data['id'],
        "amount": order_data['amount']
    }

@app.route('/payment-success')
def payment_success():
    if 'user_id' not in session:
        return redirect('/')

    user_id = session['user_id']
    cart_items = CartItem.query.filter_by(user_id=user_id).all()

    total = sum(item.product.price * item.quantity for item in cart_items)
    product_names = ", ".join([item.product.name for item in cart_items])
    quantity = sum(item.quantity for item in cart_items)

    new_order = Order(
        user_id=user_id,
        product_name=product_names,
        total_price=total,
        quantity=quantity,
        address="Saved Address",
        status="Processing"
    )

    db.session.add(new_order)
    db.session.query(CartItem).filter_by(user_id=user_id).delete()
    db.session.commit()

    return redirect('/my-orders')

if __name__ == '__main__':
    app.run(debug=True)

