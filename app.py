#########################
# app.py
#########################

from flask import Flask, render_template, request, redirect, url_for, send_file, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import LETTER
from io import BytesIO

app = Flask(__name__)
app.secret_key = "MI_SECRETO_SUPER_SEGURO"  # Cambia esto en producción

# Configuración de la base de datos (SQLite local)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///productos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#################################
# Flask-Login Login
#################################
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'  # Si no está logueado y se requiere login, redirige a 'index'

#################################
# MODELOS: User y Product
#################################

class User(UserMixin, db.Model):
    """
    Modelo para usuarios, con UserMixin para Flask-Login.
    """
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), default='user')  # 'admin' o 'user'

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    marca = db.Column(db.String(100), nullable=True)
    codigo = db.Column(db.String(50), nullable=True)
    precio_base = db.Column(db.Float, nullable=False, default=0.0)
    porcentaje_impuestos = db.Column(db.Float, nullable=False, default=0.0)
    porcentaje_ganancia = db.Column(db.Float, nullable=False, default=0.0)
    potencia = db.Column(db.Float, nullable=True, default=0.0)
    voltaje_maximo = db.Column(db.Float, nullable=True, default=0.0)
    string_count = db.Column(db.Integer, nullable=True, default=0)
    amperaje_maximo = db.Column(db.Float, nullable=True, default=0.0)
    # Tipo: inversor, panel, protecciones_cc, protecciones_ca, estructura, cable, fichas...
    tipo = db.Column(db.String(50), nullable=False)

    @property
    def precio_final(self):
        """
        Calcula el precio final aplicando impuestos y ganancia:
        precio_base * (1 + %impuestos/100) * (1 + %ganancia/100)
        """
        return self.precio_base * (1 + self.porcentaje_impuestos / 100) * (1 + self.porcentaje_ganancia / 100)

    def __repr__(self):
        return f"<Product {self.nombre} ({self.tipo})>"

#################################
# Crear la base de datos
#################################
with app.app_context():
    db.create_all()

#################################
# Flask-Login Loader
#################################
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

#################################
# Rutas de Registro/Login/Logout
#################################

@app.route('/', methods=['GET', 'POST'])
def index():
    """
    Página de inicio. Si el usuario no está logueado, se muestra un formulario de login.
    Si está logueado, se muestra un mensaje de bienvenida y el botón de logout.
    """
    if request.method == 'POST':
        # Procesar login
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            login_user(user)
            flash("Has iniciado sesión exitosamente.", "success")
            return redirect(url_for('index'))
        else:
            flash("Usuario/Contraseña inválidos", "danger")
            return redirect(url_for('index'))
    else:
        return render_template('index.html')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("Sesión cerrada.", "info")
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    """
    Permite crear un nuevo usuario. Puedes restringirlo sólo a admins, etc.
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'user')  # por defecto user
        if not username or not password:
            flash("Complete todos los campos.", "warning")
            return redirect(url_for('register'))

        # Verificar si ya existe
        if User.query.filter_by(username=username).first():
            flash("Ese usuario ya existe.", "danger")
            return redirect(url_for('register'))

        # Crear user
        new_user = User(username=username, role=role)
        new_user.set_password(password)
        db.session.add(new_user)
        db.session.commit()
        flash("Usuario creado exitosamente.", "success")
        return redirect(url_for('index'))
    else:
        return render_template('register.html')


#################################
# Rutas de CRUD para productos
#################################

@app.route('/products')
@login_required
def list_products():
    """
    Listar productos (solo usuarios logueados).
    """
    products = Product.query.order_by(Product.id).all()
    return render_template('products.html', products=products)

@app.route('/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    """
    Crear un nuevo producto.
    Solo debería poder hacerlo un usuario con role=admin (por ejemplo).
    """
    if current_user.role != 'admin':
        flash("No tienes permiso para crear productos.", "danger")
        return redirect(url_for('list_products'))

    if request.method == 'POST':
        try:
            nombre = request.form['nombre']
            marca = request.form.get('marca', '')
            codigo = request.form.get('codigo', '')
            precio_base = float(request.form.get('precio_base', 0))
            porcentaje_impuestos = float(request.form.get('porcentaje_impuestos', 0))
            porcentaje_ganancia = float(request.form.get('porcentaje_ganancia', 0))
            potencia = float(request.form.get('potencia', 0))
            voltaje_maximo = float(request.form.get('voltaje_maximo', 0))
            string_count = int(request.form.get('string_count', 0))
            amperaje_maximo = float(request.form.get('amperaje_maximo', 0))
            tipo = request.form['tipo']

            p = Product(
                nombre=nombre,
                marca=marca,
                codigo=codigo,
                precio_base=precio_base,
                porcentaje_impuestos=porcentaje_impuestos,
                porcentaje_ganancia=porcentaje_ganancia,
                potencia=potencia,
                voltaje_maximo=voltaje_maximo,
                string_count=string_count,
                amperaje_maximo=amperaje_maximo,
                tipo=tipo
            )
            db.session.add(p)
            db.session.commit()
            flash("Producto creado exitosamente.", "success")
            return redirect(url_for('list_products'))
        except Exception as e:
            flash(f"Error al crear el producto: {e}", "danger")
            return redirect(url_for('list_products'))
    else:
        return render_template('product_form.html', action="new")

@app.route('/products/edit/<int:product_id>', methods=['GET', 'POST'])
@login_required
def edit_product(product_id):
    """
    Editar un producto existente. Sólo para admin.
    """
    if current_user.role != 'admin':
        flash("No tienes permiso para editar productos.", "danger")
        return redirect(url_for('list_products'))

    product = Product.query.get_or_404(product_id)

    if request.method == 'POST':
        try:
            product.nombre = request.form['nombre']
            product.marca = request.form.get('marca', '')
            product.codigo = request.form.get('codigo', '')
            product.precio_base = float(request.form.get('precio_base', 0))
            product.porcentaje_impuestos = float(request.form.get('porcentaje_impuestos', 0))
            product.porcentaje_ganancia = float(request.form.get('porcentaje_ganancia', 0))
            product.potencia = float(request.form.get('potencia', 0))
            product.voltaje_maximo = float(request.form.get('voltaje_maximo', 0))
            product.string_count = int(request.form.get('string_count', 0))
            product.amperaje_maximo = float(request.form.get('amperaje_maximo', 0))
            product.tipo = request.form['tipo']

            db.session.commit()
            flash("Producto editado exitosamente.", "success")
            return redirect(url_for('list_products'))
        except Exception as e:
            flash(f"Error al editar el producto: {e}", "danger")
            return redirect(url_for('list_products'))
    else:
        return render_template('product_form.html', action="edit", product=product)

@app.route('/products/delete/<int:product_id>', methods=['POST'])
@login_required
def delete_product(product_id):
    """
    Borrar un producto. Sólo para admin.
    """
    if current_user.role != 'admin':
        flash("No tienes permiso para eliminar productos.", "danger")
        return redirect(url_for('list_products'))

    product = Product.query.get_or_404(product_id)
    try:
        db.session.delete(product)
        db.session.commit()
        flash("Producto eliminado correctamente.", "success")
    except Exception as e:
        flash(f"Error al eliminar el producto: {e}", "danger")
    return redirect(url_for('list_products'))

############################################
# Rutas para ingreso de consumos
############################################

@app.route('/consumo', methods=['GET', 'POST'])
@login_required
def consumo():
    """
    Muestra un formulario para ingresar 12 meses de consumo.
    Sólo usuarios logueados.
    """
    if request.method == 'POST':
        # Tomamos 12 valores de consumo
        consumos = []
        for i in range(1, 13):
            try:
                val = float(request.form.get(f'mes{i}', 0))
            except:
                val = 0
            consumos.append(val)

        # Sumamos todo el consumo anual
        consumo_anual = sum(consumos)
        # Calculamos promedio mensual
        promedio_mensual = consumo_anual / 12.0 if consumos else 0

        # Mostramos resultados y damos opción de armar presupuesto
        return render_template('consumo_resultado.html',
                               consumos=consumos,
                               consumo_anual=consumo_anual,
                               promedio_mensual=promedio_mensual)
    else:
        return render_template('consumo.html')

############################################
# Ruta para armar el presupuesto manualmente
############################################
@app.route('/armar_presupuesto', methods=['POST'])
@login_required
def armar_presupuesto():
    """
    Muestra la pantalla donde el usuario elige manualmente
    los productos por categoría, usando los datos de consumo.
    """
    try:
        consumo_anual = float(request.form.get('consumo_anual', 0))
        promedio_mensual = float(request.form.get('promedio_mensual', 0))
    except:
        flash("No se encontraron datos de consumo. Ingresa nuevamente.", "warning")
        return redirect(url_for('consumo'))

    # Agrupamos productos por tipo
    inversores = Product.query.filter_by(tipo='inversor').all()
    paneles = Product.query.filter_by(tipo='panel').all()
    protecciones_cc = Product.query.filter_by(tipo='protecciones_cc').all()
    protecciones_ca = Product.query.filter_by(tipo='protecciones_ca').all()
    estructuras = Product.query.filter_by(tipo='estructura').all()
    cables = Product.query.filter_by(tipo='cable').all()
    fichas = Product.query.filter_by(tipo='fichas').all()

    return render_template('armar_presupuesto.html',
                           consumo_anual=consumo_anual,
                           promedio_mensual=promedio_mensual,
                           inversores=inversores,
                           paneles=paneles,
                           protecciones_cc=protecciones_cc,
                           protecciones_ca=protecciones_ca,
                           estructuras=estructuras,
                           cables=cables,
                           fichas=fichas)

@app.route('/generar_presupuesto', methods=['POST'])
@login_required
def generar_presupuesto():
    """
    Genera un PDF con los productos seleccionados manualmente
    y muestra el consumo anual y promedio.
    """
    try:
        consumo_anual = float(request.form.get('consumo_anual', 0))
        promedio_mensual = float(request.form.get('promedio_mensual', 0))
    except:
        flash("No se encontraron datos de consumo para generar PDF.", "warning")
        return redirect(url_for('consumo'))

    # Recoger las selecciones del usuario
    seleccion_inversor_id = request.form.get('inversor')
    seleccion_panel_id = request.form.get('panel')
    seleccion_protecciones_cc_id = request.form.get('protecciones_cc')
    seleccion_protecciones_ca_id = request.form.get('protecciones_ca')
    seleccion_estructura_id = request.form.get('estructura')
    seleccion_cable_id = request.form.get('cable')
    seleccion_fichas_id = request.form.get('fichas')

    # Cantidades (por defecto 1)
    qty_inversor = int(request.form.get('qty_inversor', 1))
    qty_panel = int(request.form.get('qty_panel', 1))
    qty_protecciones_cc = int(request.form.get('qty_protecciones_cc', 1))
    qty_protecciones_ca = int(request.form.get('qty_protecciones_ca', 1))
    qty_estructura = int(request.form.get('qty_estructura', 1))
    qty_cable = int(request.form.get('qty_cable', 1))
    qty_fichas = int(request.form.get('qty_fichas', 1))

    # Función auxiliar para obtener producto por ID
    def get_product_by_id(pid):
        if pid and pid.isdigit():
            return Product.query.get(int(pid))
        return None

    # Obtenemos productos seleccionados
    inversor = get_product_by_id(seleccion_inversor_id)
    panel = get_product_by_id(seleccion_panel_id)
    proteccion_cc = get_product_by_id(seleccion_protecciones_cc_id)
    proteccion_ca = get_product_by_id(seleccion_protecciones_ca_id)
    estructura = get_product_by_id(seleccion_estructura_id)
    cable = get_product_by_id(seleccion_cable_id)
    fichas = get_product_by_id(seleccion_fichas_id)

    # Calcular costo total
    items_seleccionados = []
    costo_total = 0.0

    def agregar_item(producto, cantidad):
        nonlocal costo_total
        if producto and cantidad > 0:
            subtotal = producto.precio_final * cantidad
            items_seleccionados.append((producto, cantidad, subtotal))
            costo_total += subtotal

    # Agregamos cada producto a la lista
    agregar_item(inversor, qty_inversor)
    agregar_item(panel, qty_panel)
    agregar_item(proteccion_cc, qty_protecciones_cc)
    agregar_item(proteccion_ca, qty_protecciones_ca)
    agregar_item(estructura, qty_estructura)
    agregar_item(cable, qty_cable)
    agregar_item(fichas, qty_fichas)

    # Generamos PDF en memoria
    pdf_buffer = generar_pdf_presupuesto(
        consumo_anual=consumo_anual,
        promedio_mensual=promedio_mensual,
        items=items_seleccionados,
        costo_total=costo_total
    )

    return send_file(pdf_buffer,
                     as_attachment=True,
                     download_name='presupuesto_solar.pdf',
                     mimetype='application/pdf')

#################################
# Generación del PDF
#################################
def generar_pdf_presupuesto(consumo_anual, promedio_mensual, items, costo_total):
    """
    Genera un PDF en memoria con el resumen del presupuesto
    usando la librería reportlab.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=LETTER)
    c.setTitle("Presupuesto Manual de Instalación Solar")

    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 750, "Presupuesto Manual de Instalación Solar")
    c.setFont("Helvetica", 12)

    y = 700
    c.drawString(50, y, f"Consumo anual: {consumo_anual:.2f} kWh")
    y -= 20
    c.drawString(50, y, f"Promedio mensual: {promedio_mensual:.2f} kWh")
    y -= 40

    c.drawString(50, y, "Productos seleccionados:")
    y -= 20

    for prod, qty, subtotal in items:
        texto = (f"{qty} x {prod.nombre} "
                 f"(Tipo: {prod.tipo}, Código: {prod.codigo}) "
                 f"Precio Final c/u: ${prod.precio_final:.2f}  "
                 f"Subtotal: ${subtotal:.2f}")
        c.drawString(50, y, texto)
        y -= 20
        if y < 100:  # Salto de página básico
            c.showPage()
            c.setFont("Helvetica", 12)
            y = 700

    y -= 20
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, f"COSTO TOTAL: ${costo_total:.2f}")

    c.showPage()
    c.save()
    buffer.seek(0)
    return buffer

#################################
# Ejecutar la aplicación
#################################
if __name__ == '__main__':
    app.run(debug=True)
