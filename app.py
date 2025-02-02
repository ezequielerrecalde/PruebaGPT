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
import csv
import json

app = Flask(__name__)
app.secret_key = "MI_SECRETO_SUPER_SEGURO"  # Cambia esto en producción

# Configuración de la base de datos (SQLite local)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///productos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

#################################
# Flask-Login
#################################
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'index'

#################################
# MODELOS: User y Product
#################################

class User(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    # Los roles posibles: 'admin', 'user' (único usuario general) o 'instalador'
    role = db.Column(db.String(20), default='user')

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
    # 'tipo' define la categoría: inversor, panel, protecciones_cc, protecciones_ca, estructura, cable, fichas
    tipo = db.Column(db.String(50), nullable=False)
    # Campo para almacenar en formato JSON las características específicas según la categoría
    detalles = db.Column(db.Text, nullable=True, default="{}")

    @property
    def precio_final(self):
        return self.precio_base * (1 + self.porcentaje_impuestos/100) * (1 + self.porcentaje_ganancia/100)

    def __repr__(self):
        return f"<Product {self.nombre} ({self.tipo})>"

#################################
# Crear la base de datos y el usuario admin fijo
#################################
with app.app_context():
    db.create_all()
    admin = User.query.filter_by(username='ezequiel1407').first()
    if not admin:
        admin = User(username='ezequiel1407', role='admin')
        admin.set_password('larenga73')
        db.session.add(admin)
        db.session.commit()

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
    Página de inicio.
    Si no se ha iniciado sesión se muestra el formulario de login.
    """
    if request.method == 'POST':
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
    Permite crear un nuevo usuario.
    No se permite registrar el rol 'admin' y sólo se permite un usuario general (rol 'user').
    """
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        role = request.form.get('role', 'user')  # Opciones: 'user' o 'instalador'
        if not username or not password:
            flash("Complete todos los campos.", "warning")
            return redirect(url_for('register'))
        if role == 'admin':
            flash("No se puede registrar el rol admin.", "danger")
            return redirect(url_for('register'))
        if role == 'user' and User.query.filter_by(role='user').first():
            flash("Ya existe un usuario general registrado.", "danger")
            return redirect(url_for('register'))
        if User.query.filter_by(username=username).first():
            flash("Ese usuario ya existe.", "danger")
            return redirect(url_for('register'))
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
    Lista los productos agrupados por categoría.
    Los usuarios 'admin' ven datos completos (incluyendo precio base, % de impuestos y ganancia, y botones CRUD),
    mientras que los demás ven únicamente los datos técnicos y el precio final.
    """
    inversores = Product.query.filter_by(tipo='inversor').all()
    paneles = Product.query.filter_by(tipo='panel').all()
    protecciones_cc = Product.query.filter_by(tipo='protecciones_cc').all()
    protecciones_ca = Product.query.filter_by(tipo='protecciones_ca').all()
    estructuras = Product.query.filter_by(tipo='estructura').all()
    cables = Product.query.filter_by(tipo='cable').all()
    fichas = Product.query.filter_by(tipo='fichas').all()
    return render_template('products.html',
                           inversores=inversores,
                           paneles=paneles,
                           protecciones_cc=protecciones_cc,
                           protecciones_ca=protecciones_ca,
                           estructuras=estructuras,
                           cables=cables,
                           fichas=fichas)

@app.route('/products/new', methods=['GET', 'POST'])
@login_required
def new_product():
    """
    Crea un producto manualmente (formulario clásico).
    Solo el usuario admin puede acceder a esta opción.
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
                tipo=tipo,
                detalles="{}"
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
    Edita un producto existente.
    Solo el usuario admin tiene permiso para esta acción.
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
    Elimina un producto.
    Solo el usuario admin puede realizar esta acción.
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

#################################
# Ruta de carga de productos vía CSV (Excel)
#################################
@app.route('/upload_products', methods=['GET', 'POST'])
@login_required
def upload_products():
    """
    Permite al usuario admin subir un archivo CSV con productos para una categoría específica.
    Se asignan valores por defecto ("N/A" o 0) en los campos faltantes, y se almacenan los datos
    específicos en el campo 'detalles' (formato JSON).
    Además, se ofrece la opción de descargar un CSV de ejemplo.
    """
    if current_user.role != 'admin':
        flash("No tienes permiso para subir productos.", "danger")
        return redirect(url_for('list_products'))
    if request.method == 'POST':
        categoria = request.form.get('categoria')
        if not categoria:
            flash("Debes seleccionar una categoría.", "danger")
            return redirect(url_for('upload_products'))
        if 'file' not in request.files:
            flash("No se encontró el archivo.", "danger")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash("No se seleccionó ningún archivo.", "danger")
            return redirect(request.url)
        try:
            file_stream = file.stream.read().decode("utf-8").splitlines()
            reader = csv.DictReader(file_stream)
            count = 0
            for row in reader:
                if categoria == 'inversor':
                    marca = row.get('marca', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    tipo_inversor = row.get('tipo_inversor', 'N/A')
                    potencia_nominal = row.get('potencia_nominal', '0')
                    tension_entrada_cc = row.get('tension_entrada_cc', '0')
                    tension_salida_ca = row.get('tension_salida_ca', '0')
                    regulador_mppt = row.get('regulador_mppt', 'N/A')
                    corriente_max_por_string = row.get('corriente_max_por_string', '0')
                    potencia_max_paneles = row.get('potencia_max_paneles', '0')
                    conectividad = row.get('conectividad', 'N/A')
                    tipo_proteccion_cc = row.get('tipo_proteccion_cc', 'N/A')
                    proteccion_cc = row.get('proteccion_cc', 'N/A')
                    tipo_proteccion_ca = row.get('tipo_proteccion_ca', 'N/A')
                    proteccion_ca = row.get('proteccion_ca', 'N/A')
                    try:
                        precio_base = float(row.get('precio_base', 0))
                    except:
                        precio_base = 0.0
                    try:
                        porcentaje_impuestos = float(row.get('porcentaje_impuestos', 0))
                    except:
                        porcentaje_impuestos = 0.0
                    try:
                        porcentaje_ganancia = float(row.get('porcentaje_ganancia', 0))
                    except:
                        porcentaje_ganancia = 0.0
                    product = Product(
                        nombre=modelo,
                        marca=marca,
                        codigo=tipo_inversor,
                        precio_base=precio_base,
                        porcentaje_impuestos=porcentaje_impuestos,
                        porcentaje_ganancia=porcentaje_ganancia,
                        potencia=float(potencia_nominal) if potencia_nominal else 0.0,
                        voltaje_maximo=float(tension_salida_ca) if tension_salida_ca else 0.0,
                        string_count=int(float(corriente_max_por_string)) if corriente_max_por_string else 0,
                        amperaje_maximo=0.0,
                        tipo='inversor',
                        detalles=json.dumps({
                            "tipo_inversor": tipo_inversor,
                            "potencia_nominal": potencia_nominal,
                            "tension_entrada_cc": tension_entrada_cc,
                            "tension_salida_ca": tension_salida_ca,
                            "regulador_mppt": regulador_mppt,
                            "corriente_max_por_string": corriente_max_por_string,
                            "potencia_max_paneles": potencia_max_paneles,
                            "conectividad": conectividad,
                            "tipo_proteccion_cc": tipo_proteccion_cc,
                            "proteccion_cc": proteccion_cc,
                            "tipo_proteccion_ca": tipo_proteccion_ca,
                            "proteccion_ca": proteccion_ca
                        })
                    )
                elif categoria == 'panel':
                    proveedor = row.get('proveedor', 'N/A')
                    marca = row.get('marca', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    potencia = row.get('potencia', '0')
                    voltaje = row.get('voltaje', '0')
                    tension = row.get('tension', '0')
                    tipo_panel = row.get('tipo_panel', 'N/A')
                    try:
                        precio_base = float(row.get('precio_base', 0))
                    except:
                        precio_base = 0.0
                    try:
                        porcentaje_ganancia = float(row.get('porcentaje_ganancia', 0))
                    except:
                        porcentaje_ganancia = 0.0
                    product = Product(
                        nombre=modelo,
                        marca=marca,
                        codigo='',
                        precio_base=precio_base,
                        porcentaje_impuestos=0.0,
                        porcentaje_ganancia=porcentaje_ganancia,
                        potencia=float(potencia) if potencia else 0.0,
                        voltaje_maximo=float(voltaje) if voltaje else 0.0,
                        string_count=0,
                        amperaje_maximo=0.0,
                        tipo='panel',
                        detalles=json.dumps({
                            "proveedor": proveedor,
                            "potencia": potencia,
                            "voltaje": voltaje,
                            "tension": tension,
                            "tipo_panel": tipo_panel
                        })
                    )
                elif categoria in ['protecciones_cc', 'protecciones_ca']:
                    marca = row.get('marca', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    proveedor = row.get('proveedor', 'N/A')
                    try:
                        precio_base = float(row.get('precio_base', 0))
                    except:
                        precio_base = 0.0
                    try:
                        porcentaje_ganancia = float(row.get('porcentaje_ganancia', 0))
                    except:
                        porcentaje_ganancia = 0.0
                    ubicacion = row.get('ubicacion', 'N/A')
                    tension_nominal_operacion = row.get('tension_nominal_operacion', '0')
                    corriente_descarga_nominal = row.get('corriente_descarga_nominal', '0')
                    corriente_descarga_maxima = row.get('corriente_descarga_maxima', '0')
                    tecnologia_proteccion = row.get('tecnologia_proteccion', 'N/A')
                    clase_proteccion = row.get('clase_proteccion', 'N/A')
                    indicador_estado = row.get('indicador_estado', 'N/A')
                    montaje_caja = row.get('montaje_caja', 'N/A')
                    product = Product(
                        nombre=modelo,
                        marca=marca,
                        codigo='',
                        precio_base=precio_base,
                        porcentaje_impuestos=0.0,
                        porcentaje_ganancia=porcentaje_ganancia,
                        potencia=0.0,
                        voltaje_maximo=0.0,
                        string_count=0,
                        amperaje_maximo=0.0,
                        tipo=categoria,
                        detalles=json.dumps({
                            "proveedor": proveedor,
                            "ubicacion": ubicacion,
                            "tension_nominal_operacion": tension_nominal_operacion,
                            "corriente_descarga_nominal": corriente_descarga_nominal,
                            "corriente_descarga_maxima": corriente_descarga_maxima,
                            "tecnologia_proteccion": tecnologia_proteccion,
                            "clase_proteccion": clase_proteccion,
                            "indicador_estado": indicador_estado,
                            "montaje_caja": montaje_caja
                        })
                    )
                elif categoria == 'estructura':
                    proveedor = row.get('proveedor', 'N/A')
                    marca = row.get('marca', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    tipo_estructura = row.get('tipo_estructura', 'N/A')
                    cantidad_paneles = row.get('cantidad_paneles', '0')
                    material = row.get('material', 'N/A')
                    inclinacion = row.get('inclinacion', '0')
                    try:
                        precio_base = float(row.get('precio_base', 0))
                    except:
                        precio_base = 0.0
                    try:
                        porcentaje_ganancia = float(row.get('porcentaje_ganancia', 0))
                    except:
                        porcentaje_ganancia = 0.0
                    product = Product(
                        nombre=modelo,
                        marca=marca,
                        codigo='',
                        precio_base=precio_base,
                        porcentaje_impuestos=0.0,
                        porcentaje_ganancia=porcentaje_ganancia,
                        potencia=0.0,
                        voltaje_maximo=0.0,
                        string_count=0,
                        amperaje_maximo=0.0,
                        tipo='estructura',
                        detalles=json.dumps({
                            "proveedor": proveedor,
                            "tipo_estructura": tipo_estructura,
                            "cantidad_paneles": cantidad_paneles,
                            "material": material,
                            "inclinacion": inclinacion
                        })
                    )
                elif categoria == 'cable':
                    proveedor = row.get('proveedor', 'N/A')
                    marca = row.get('marca', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    tipo_cable = row.get('tipo_cable', 'N/A')
                    espesor = row.get('espesor', '0')
                    tipo_baina = row.get('tipo_baina', 'N/A')
                    try:
                        precio_base = float(row.get('precio_base', 0))
                    except:
                        precio_base = 0.0
                    try:
                        porcentaje_ganancia = float(row.get('porcentaje_ganancia', 0))
                    except:
                        porcentaje_ganancia = 0.0
                    product = Product(
                        nombre=modelo,
                        marca=marca,
                        codigo='',
                        precio_base=precio_base,
                        porcentaje_impuestos=0.0,
                        porcentaje_ganancia=porcentaje_ganancia,
                        potencia=0.0,
                        voltaje_maximo=0.0,
                        string_count=0,
                        amperaje_maximo=0.0,
                        tipo='cable',
                        detalles=json.dumps({
                            "proveedor": proveedor,
                            "tipo_cable": tipo_cable,
                            "espesor": espesor,
                            "tipo_baina": tipo_baina
                        })
                    )
                elif categoria == 'fichas':
                    tipo_ficha = row.get('tipo_ficha', 'N/A')
                    marca = row.get('marca', 'N/A')
                    modelo = row.get('modelo', 'N/A')
                    proveedor = row.get('proveedor', 'N/A')
                    try:
                        precio_base = float(row.get('precio_base', 0))
                    except:
                        precio_base = 0.0
                    try:
                        porcentaje_ganancia = float(row.get('porcentaje_ganancia', 0))
                    except:
                        porcentaje_ganancia = 0.0
                    product = Product(
                        nombre=modelo,
                        marca=marca,
                        codigo='',
                        precio_base=precio_base,
                        porcentaje_impuestos=0.0,
                        porcentaje_ganancia=porcentaje_ganancia,
                        potencia=0.0,
                        voltaje_maximo=0.0,
                        string_count=0,
                        amperaje_maximo=0.0,
                        tipo='fichas',
                        detalles=json.dumps({
                            "tipo_ficha": tipo_ficha,
                            "proveedor": proveedor
                        })
                    )
                else:
                    continue
                db.session.add(product)
                count += 1
            db.session.commit()
            flash(f'Se han cargado {count} productos correctamente.', 'success')
            return redirect(url_for('list_products'))
        except Exception as e:
            flash(f'Error al procesar el archivo: {e}', 'danger')
            return redirect(request.url)
    else:
        return render_template('upload_products.html')

#################################
# Ruta para descargar archivo CSV de ejemplo
#################################
@app.route('/download_sample/<categoria>')
@login_required
def download_sample(categoria):
    if current_user.role != 'admin':
        flash("No tienes permiso para descargar el ejemplo.", "danger")
        return redirect(url_for('upload_products'))
    output = []
    if categoria == 'inversor':
        headers = ['marca', 'modelo', 'tipo_inversor', 'potencia_nominal', 'tension_entrada_cc', 'tension_salida_ca', 'regulador_mppt', 'corriente_max_por_string', 'potencia_max_paneles', 'conectividad', 'tipo_proteccion_cc', 'proteccion_cc', 'tipo_proteccion_ca', 'proteccion_ca', 'precio_base', 'porcentaje_impuestos', 'porcentaje_ganancia']
        example = ['MarcaX', 'ModeloY', 'TipoA', '500', '300', '230', 'Si', '10', '600', 'WiFi', 'Interior', 'Protegido', 'Exterior', 'No', '1000', '15', '20']
    elif categoria == 'panel':
        headers = ['proveedor', 'marca', 'modelo', 'potencia', 'voltaje', 'tension', 'tipo_panel', 'precio_base', 'porcentaje_ganancia']
        example = ['ProveedorZ', 'MarcaP', 'ModeloQ', '250', '40', '35', 'Tipo1', '500', '25']
    elif categoria in ['protecciones_cc', 'protecciones_ca']:
        headers = ['marca', 'modelo', 'proveedor', 'precio_base', 'porcentaje_ganancia', 'ubicacion', 'tension_nominal_operacion', 'corriente_descarga_nominal', 'corriente_descarga_maxima', 'tecnologia_proteccion', 'clase_proteccion', 'indicador_estado', 'montaje_caja']
        example = ['MarcaR', 'ModeloS', 'ProveedorT', '200', '30', 'Tablero', '230', '5', '10', 'MOV', 'TipoII', 'LED', 'Cuadro']
    elif categoria == 'estructura':
        headers = ['proveedor', 'marca', 'modelo', 'tipo_estructura', 'cantidad_paneles', 'material', 'inclinacion', 'precio_base', 'porcentaje_ganancia']
        example = ['ProveedorU', 'MarcaV', 'ModeloW', 'TipoE', '10', 'Aluminio', '30', '800', '20']
    elif categoria == 'cable':
        headers = ['proveedor', 'marca', 'modelo', 'tipo_cable', 'espesor', 'tipo_baina', 'precio_base', 'porcentaje_ganancia']
        example = ['ProveedorX', 'MarcaY', 'ModeloZ', 'TipoC', '2.5', 'Aislado', '100', '15']
    elif categoria == 'fichas':
        headers = ['tipo_ficha', 'marca', 'modelo', 'proveedor', 'precio_base', 'porcentaje_ganancia']
        example = ['TipoF', 'MarcaG', 'ModeloH', 'ProveedorI', '50', '10']
    else:
        flash("Categoría desconocida.", "danger")
        return redirect(url_for('upload_products'))
    output.append(','.join(headers))
    output.append(','.join(example))
    csv_data = "\n".join(output)
    return send_file(BytesIO(csv_data.encode('utf-8')),
                     as_attachment=True,
                     download_name=f'sample_{categoria}.csv',
                     mimetype='text/csv')

#################################
# Rutas para ingreso de consumos
#################################
@app.route('/consumo', methods=['GET', 'POST'])
@login_required
def consumo():
    if request.method == 'POST':
        consumos = []
        for i in range(1, 13):
            try:
                val = float(request.form.get(f'mes{i}', 0))
            except:
                val = 0
            consumos.append(val)
        consumo_anual = sum(consumos)
        promedio_mensual = consumo_anual / 12.0 if consumos else 0
        return render_template('consumo_resultado.html',
                               consumos=consumos,
                               consumo_anual=consumo_anual,
                               promedio_mensual=promedio_mensual)
    else:
        return render_template('consumo.html')

#################################
# Ruta para armar el presupuesto a partir de consumos
#################################
@app.route('/armar_presupuesto', methods=['POST'])
@login_required
def armar_presupuesto():
    """
    Muestra una pantalla en la que, basándose en el consumo (anual y promedio),
    el usuario puede seleccionar la opción más adecuada para cada una de las 7 categorías.
    Luego se usará esa información para generar un informe técnico y presupuesto.
    """
    try:
        consumo_anual = float(request.form.get('consumo_anual', 0))
        promedio_mensual = float(request.form.get('promedio_mensual', 0))
    except:
        flash("No se encontraron datos de consumo. Ingresa nuevamente.", "warning")
        return redirect(url_for('consumo'))
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

#################################
# Ruta para generar el presupuesto (PDF)
#################################
@app.route('/generar_presupuesto', methods=['POST'])
@login_required
def generar_presupuesto():
    try:
        consumo_anual = float(request.form.get('consumo_anual', 0))
        promedio_mensual = float(request.form.get('promedio_mensual', 0))
    except:
        flash("No se encontraron datos de consumo para generar PDF.", "warning")
        return redirect(url_for('consumo'))
    seleccion_inversor_id = request.form.get('inversor')
    seleccion_panel_id = request.form.get('panel')
    seleccion_protecciones_cc_id = request.form.get('protecciones_cc')
    seleccion_protecciones_ca_id = request.form.get('protecciones_ca')
    seleccion_estructura_id = request.form.get('estructura')
    seleccion_cable_id = request.form.get('cable')
    seleccion_fichas_id = request.form.get('fichas')
    qty_inversor = int(request.form.get('qty_inversor', 1))
    qty_panel = int(request.form.get('qty_panel', 1))
    qty_protecciones_cc = int(request.form.get('qty_protecciones_cc', 1))
    qty_protecciones_ca = int(request.form.get('qty_protecciones_ca', 1))
    qty_estructura = int(request.form.get('qty_estructura', 1))
    qty_cable = int(request.form.get('qty_cable', 1))
    qty_fichas = int(request.form.get('qty_fichas', 1))
    def get_product_by_id(pid):
        if pid and pid.isdigit():
            return Product.query.get(int(pid))
        return None
    inversor = get_product_by_id(seleccion_inversor_id)
    panel = get_product_by_id(seleccion_panel_id)
    proteccion_cc = get_product_by_id(seleccion_protecciones_cc_id)
    proteccion_ca = get_product_by_id(seleccion_protecciones_ca_id)
    estructura = get_product_by_id(seleccion_estructura_id)
    cable = get_product_by_id(seleccion_cable_id)
    fichas = get_product_by_id(seleccion_fichas_id)
    items_seleccionados = []
    costo_total = 0.0
    def agregar_item(producto, cantidad):
        nonlocal costo_total
        if producto and cantidad > 0:
            subtotal = producto.precio_final * cantidad
            items_seleccionados.append((producto, cantidad, subtotal))
            costo_total += subtotal
    agregar_item(inversor, qty_inversor)
    agregar_item(panel, qty_panel)
    agregar_item(proteccion_cc, qty_protecciones_cc)
    agregar_item(proteccion_ca, qty_protecciones_ca)
    agregar_item(estructura, qty_estructura)
    agregar_item(cable, qty_cable)
    agregar_item(fichas, qty_fichas)
    pdf_buffer = generar_pdf_presupuesto(consumo_anual, promedio_mensual, items_seleccionados, costo_total)
    return send_file(pdf_buffer,
                     as_attachment=True,
                     download_name='presupuesto_solar.pdf',
                     mimetype='application/pdf')

#################################
# Función para generar el PDF
#################################
def generar_pdf_presupuesto(consumo_anual, promedio_mensual, items, costo_total):
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
        texto = (f"{qty} x {prod.nombre} (Tipo: {prod.tipo}, Código: {prod.codigo}) "
                 f"Precio Final c/u: ${prod.precio_final:.2f}  Subtotal: ${subtotal:.2f}")
        c.drawString(50, y, texto)
        y -= 20
        if y < 100:
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
