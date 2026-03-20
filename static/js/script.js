// Open modal — uses flex display for new centered layout
function openModal(id) {
    var modal = document.getElementById(id);
    if (modal) {
        modal.style.display = 'flex';
        document.body.style.overflow = 'hidden';
    }
}

// Close modal
function closeModal(id) {
    var modal = document.getElementById(id);
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

// Close modal if clicked on the overlay (outside card)
window.onclick = function (event) {
    var modals = ['loginModal', 'signupModal', 'resetModal'];
    modals.forEach(function (id) {
        var modal = document.getElementById(id);
        if (modal && event.target === modal) {
            closeModal(id);
        }
    });
};

// Close modals on Escape key
document.addEventListener('keydown', function (e) {
    if (e.key === 'Escape') {
        ['loginModal', 'signupModal', 'resetModal'].forEach(closeModal);
    }
});

// Newsletter form handler
function handleNewsletterSignup(e) {
    e.preventDefault();
    var input = document.getElementById('newsletter-email');
    if (input && input.value) {
        var btn = e.target.querySelector('button');
        btn.textContent = 'Thank You!';
        btn.style.background = '#22863a';
        input.value = '';
        setTimeout(function () {
            btn.textContent = 'Subscribe';
            btn.style.background = '';
        }, 3000);
    }
}

// Dropdown click-to-toggle
document.addEventListener('DOMContentLoaded', function() {
    const megaBtn = document.querySelector('.mega-dropbtn');
    const megaDropdownContent = document.querySelector('.mega-dropdown-content');
    const megaDropdownContainer = document.querySelector('.mega-dropdown');
    
    if (megaBtn && megaDropdownContent) {
        megaBtn.addEventListener('click', function(e) {
            e.preventDefault();
            megaDropdownContent.classList.toggle('show-mega');
        });
        
        // Close dropdown when clicking outside
        document.addEventListener('click', function(e) {
            if (megaDropdownContainer && !megaDropdownContainer.contains(e.target)) {
                megaDropdownContent.classList.remove('show-mega');
            }
        });
    }
});

// --- CART DRAWER LOGIC ---
async function openCartDrawer() {
    const overlay = document.querySelector('.cart-overlay');
    const drawer = document.getElementById('cart-drawer');
    const content = document.getElementById('cart-drawer-content');
    
    // Show loading state
    content.innerHTML = '<div style="padding:40px; text-align:center;">Loading cart...</div>';
    
    overlay.classList.add('open');
    drawer.classList.add('open');
    document.body.style.overflow = 'hidden';

    try {
        const res = await fetch('/api/cart/drawer');
        const html = await res.text();
        content.innerHTML = html;
    } catch(e) {
        content.innerHTML = '<div style="padding:40px; text-align:center; color:red;">Failed to load cart.</div>';
    }
}

function closeCartDrawer() {
    document.querySelector('.cart-overlay').classList.remove('open');
    document.getElementById('cart-drawer').classList.remove('open');
    document.body.style.overflow = '';
}

async function updateCartItem(cartId, newQuantity) {
    await fetch('/api/cart/update', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cart_id: cartId, quantity: newQuantity })
    });
    openCartDrawer();
}

async function addToCartAjax(productId) {
    const res = await fetch('/api/cart/add', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ product_id: productId })
    });
    const data = await res.json();
    if (data.error === "Not logged in") {
        openModal('loginModal');
        return;
    }
    openCartDrawer();
}

document.addEventListener('DOMContentLoaded', () => {
    const cartForms = document.querySelectorAll('form[action="/add-to-cart"]');
    cartForms.forEach(form => {
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const formData = new FormData(form);
            const productId = formData.get('product_id');
            await addToCartAjax(productId);
        });
    });
});

// ---- COUPON CODE LOGIC (global so it works with AJAX-loaded drawer) ----
async function applyDrawerCoupon() {
    const input = document.getElementById('drawer-coupon-input');
    const msgDiv = document.getElementById('drawer-coupon-msg');
    const totalEl = document.querySelector('.totals-row strong');
    if (!input) return;
    const code = input.value.trim();
    if (!code) {
        msgDiv.style.display = 'block';
        msgDiv.style.color = '#cc0000';
        msgDiv.textContent = 'Please enter a coupon code.';
        return;
    }
    try {
        const res = await fetch('/api/apply-coupon', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code })
        });
        const data = await res.json();
        if (data.success) {
            msgDiv.style.display = 'block';
            msgDiv.style.color = '#22863a';
            msgDiv.innerHTML = `✓ ${data.message} You save <strong>₹${data.discount}</strong>!`;
            if (totalEl) totalEl.textContent = '₹' + data.new_total.toFixed(2);
            const applyBtn = document.getElementById('drawer-coupon-btn');
            if (applyBtn) { applyBtn.textContent = 'Applied ✓'; applyBtn.style.background = '#22863a'; applyBtn.disabled = true; }
        } else {
            msgDiv.style.display = 'block';
            msgDiv.style.color = '#cc0000';
            msgDiv.textContent = data.error || 'Invalid coupon code.';
        }
    } catch(e) {
        msgDiv.style.display = 'block';
        msgDiv.style.color = '#cc0000';
        msgDiv.textContent = 'Something went wrong. Try again.';
    }
}
