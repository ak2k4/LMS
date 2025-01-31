from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session, g
import cx_Oracle
from flask_mail import Mail, Message
from datetime import date


app = Flask(__name__)
app.secret_key = "your_secret_key"
# Database connection setup
dsn_tns = cx_Oracle.makedsn("ltcoracle", "1521", service_name="orcl")
connection = cx_Oracle.connect(user="lmsdev", password="lmsdev", dsn=dsn_tns)
# Mail configuration
app.config["MAIL_SERVER"] = "appmail.larsentoubro.com"
app.config["MAIL_PORT"] = 25  # or 587 if using TLS
app.config["MAIL_USE_TLS"] = False  # True if using TLS
app.config["MAIL_DEFAULT_SENDER"] = "Named User Mgmt System <noreply@larsentoubro.com>"
mail = Mail(app)


@app.route("/unauthorized")
def unauthorized():
    return "Unauthorized access. Please login to access this page.", 401


LDAP_SERVER = "LTEHCHIYODADC.ENCNET.COM"
LDAP_BASE_DN = "DC=ENCNET,DC=COM"


def authenticate_ldap(username, password):
    if not password:
        return False

    server = ldap3.Server(LDAP_SERVER)
    try:
        conn = ldap3.Connection(
            server, user=f"ENCNET\\{username}", password=password, auto_bind=True
        )

        if conn.bind():
            conn.unbind()
            return True
        else:
            conn.unbind()
            return False
    except ldap3.core.exceptions.LDAPException as e:
        print(f"LDAP Exception: {e}")
        return False


@auth.verify_password
def verify_password(username, password):
    return authenticate_ldap(username, password)


@app.route("/")
@auth.login_required
def login():
    cursor = connection.cursor()
    username = auth.username()
    query = "SELECT C_NAME FROM EXTN.T_CONTACTS WHERE C_PSNO = :username"
    cursor.execute(query, {"username": username})
    result = cursor.fetchone()
    if result:
        session["name"] = result[0]
    else:
        session["name"] = None
    query = "SELECT PSNO from NUMS_ADMIN where PSNO = :username"
    cursor.execute(query,{'username': username})
    admin_name = cursor.fetchall()    
    query_dept = """SELECT D_CODE FROM EXTN.t_department d JOIN EXTN.t_contacts c ON d.d_id = c.d_id WHERE c.c_psno = :username"""
    cursor.execute(query_dept, {'username': username})

    user_department = cursor.fetchone()

  
    # Fetch distinct departments for the user
    query_dept = """SELECT D_CODE FROM EXTN.t_department d JOIN EXTN.t_contacts c ON d.d_id = c.d_id WHERE c.c_psno = :username"""
    cursor.execute(query_dept, {'username': username})
    user_department = cursor.fetchone()
    if user_department:
        deptname = user_department[0]
        # if admin_name:
        #     deptname="all"
          # Assuming taking the first department found
    else:
        deptname = "all"  # Default to "all" if no department found (adjust as per your application logic)
    cursor.close()
    return redirect(url_for("dept", location="LTEHE-VADODARA", deptname=deptname))

@app.route('/details/', defaults={'location': None, 'deptname': None})
@app.route('/details/<location>/', defaults={'deptname': None})
@app.route('/details/<location>/<deptname>/')
@auth.login_required
def dept(location, deptname):
    cursor = connection.cursor()
    username = auth.username()
    query = "SELECT PSNO from NUMS_ADMIN where PSNO = :username"
    cursor.execute(query,{'username': username})
    dept1=deptname
    print(dept1)
    admin_name = cursor.fetchall()
    query_dept = """
        SELECT D_CODE 
        FROM EXTN.t_department d 
        JOIN EXTN.t_contacts c ON d.d_id = c.d_id 
        WHERE c.c_psno = :username
    """
    cursor.execute(query_dept, {'username': username})
    user_departments = [row[0] for row in cursor.fetchall()]

    # Validate deptname against user's departments
    if not admin_name:
        if deptname and deptname not in user_departments and deptname.lower() != 'all':
        # Redirect or handle unauthorized access (e.g., return an error page)
            return "Unauthorized access"

    
    # Fetch distinct products
    query_products = "SELECT DISTINCT product FROM lmsdev.master_allocation WHERE location = :location"
    cursor.execute(query_products, {'location': location})
    distinct_products = [row[0] for row in cursor.fetchall()]
  
    # Set deptname based on user's department(s)
    
    print(deptname)
    query_distinct_locations = "SELECT DISTINCT location FROM lmsdev.master_allocation"
    cursor.execute(query_distinct_locations)
    distinct_locations = [row[0] for row in cursor.fetchall()]

    query_dept_all = "SELECT DISTINCT department FROM lmsdev.master_allocation WHERE location = :location"
    cursor.execute(query_dept_all, {'location': location})
    distinct_departments = [row[0] for row in cursor.fetchall()]
    print(distinct_departments)
    product_data = {}
    columns = []
    data = []
    for product in distinct_products:
        # if admin_name: 
            if deptname.lower() == "all" and admin_name:
                
                # Query for all departments
                count_query = """
                    SELECT COUNT(*)
                    FROM lmsdev.RLM
                    WHERE product = :product AND location = :location AND REVOKED_ON IS NULL
                """
                cursor.execute(count_query, {'product': product, 'location': location})
                count_result = cursor.fetchone()[0]
                
                total_query = """
                    SELECT SUM(allocation)
                    FROM lmsdev.master_allocation
                    WHERE product = :product AND location = :location
                """
                cursor.execute(total_query, {'product': product, 'location': location})
                total_result = cursor.fetchone()[0]

                final_query = """
                    SELECT *
                    FROM lmsdev.RLM
                    WHERE location = :location AND REVOKED_ON IS NULL 
                """
                cursor.execute(final_query, {'location': location})
            else:
                # Query for specific department
                count_query = """
                    SELECT COUNT(*)
                    FROM lmsdev.RLM
                    WHERE product = :product AND location = :location AND dept = :deptname AND REVOKED_ON IS NULL 
                """
                cursor.execute(count_query, {'product': product, 'location': location, 'deptname': deptname})
                count_result = cursor.fetchone()[0]
                
                total_query = """
                    SELECT SUM(allocation)
                    FROM lmsdev.master_allocation
                    WHERE product = :product AND department = :deptname AND location = :location
                """
                cursor.execute(total_query, {'product': product, 'deptname': deptname, 'location': location})
                total_result = cursor.fetchone()[0]

                final_query = """
                    SELECT *
                    FROM lmsdev.RLM
                    WHERE dept = :deptname AND location = :location AND REVOKED_ON IS NULL 
                """
                cursor.execute(final_query, {'deptname': deptname, 'location': location})
        
            data = cursor.fetchall()
            columns = [col[0] for col in cursor.description]
            product_data[product] = {'count': count_result, 'total': total_result}
            
    
    # Store values in session
    session['location'] = location
    session['product'] = distinct_products
    session['deptname'] = deptname
    session['a_name'] = admin_name

    cursor.close()
    
    return render_template(
        'index.html',
        # user_department=user_department,
        location=location,
        deptname=deptname,
        distinct_products=distinct_products,
        product_data=product_data,
        data=data,
        columns=columns,
        distinct_locations=distinct_locations,
        admin_name=admin_name,
        distinct_departments=distinct_departments
    )


#grant button on main page ..
@app.route('/adduser')

@auth.login_required
def Adduser():
    location = session.get('location', 'Unknown')
    product = session.get('product', [])
    deptname = session.get('deptname', 'Unknown')
    selected_product = request.args.get('selected_product')
    cursor = connection.cursor()
    
    # Fetch distinct departments only if deptname is 'all'
    if deptname.lower() == 'all':
        query_dept = "SELECT DISTINCT department FROM lmsdev.master_allocation WHERE location = :location"
        cursor.execute(query_dept, {'location': location})
        distinct_departments = [row[0] for row in cursor.fetchall()]
    else:
        distinct_departments = [deptname]  # Only use the specified department
    
    cursor.close()

    return render_template('adduser.html', 
                            location=location, 
                            distinct_departments=distinct_departments, 
                            distinct_products=product, deptname=deptname, 
                            selected_product=selected_product)

@app.route('/get_user_details', methods=['POST'])
@auth.login_required
def get_user_details():
    psno = request.json.get('psno')
    if not psno:
        return jsonify({'error': 'PS No is required'}), 400

    cursor = connection.cursor()
    query = "SELECT NAME, EMAILID FROM(SELECT NAME, EMAILID, GRANTED_ON FROM LMSDEV.RLM WHERE PSNO = :psno UNION SELECT C_NAME AS NAME,C_EMAIL AS EMAILID, SYSDATE-365 AS GRANTED_ON FROM EXTN.T_CONTACTS WHERE C_PSNO= :psno) ORDER BY GRANTED_ON DESC"
    cursor.execute(query, {'psno': psno})
    user = cursor.fetchone()
    cursor.close()

    if user:
        return jsonify({'name': user[0], 'emailid': user[1]})
    else:
        return jsonify({'error': 'User not found'}), 404

@app.route('/insert', methods=['POST'])
@auth.login_required
def insert():
    psno = request.form['psNo']
    name = request.form['name']
    location = session.get('location')
    department = request.form.get('dept', session.get('deptname'))  # Get department from form or session
    allocatelicence = request.form.get('product', session.get('product'))  # Get product from form or session
    emailid = request.form['emailId']
    loadusers = request.form['loadUsers']

    cursor = connection.cursor()
    try:
        # Check if the license is already assigned
        cursor.execute("""
            SELECT COUNT(*) FROM "LMSDEV"."RLM" 
            WHERE PSNO = :psno AND PRODUCT = :allocatelicence AND REVOKED_ON IS NULL
        """, {
            'psno': psno, 
            'allocatelicence': allocatelicence
        })
        
        count = cursor.fetchone()[0]
        if count > 0:
            # License is already assigned
            flash('Your license is already assigned', 'error')
            return redirect(url_for('access', var=psno))  # Redirect to the 'adduser' route (or wherever appropriate)
        
        # Proceed with insertion into both tables
        cursor.execute("""
            INSERT INTO "LMSDEV"."RLM" (PSNO, NAME, LOCATION, DEPT, PRODUCT, EMAILID, LOADUSERS, GRANTED_ON) 
            VALUES (:psno, :name, :location, :department, :allocatelicence, :emailid, :loadusers, SYSDATE)
        """, {
            'psno': psno, 
            'name': name, 
            'location': location, 
            'department': department, 
            'allocatelicence': allocatelicence, 
            'emailid': emailid, 
            'loadusers': loadusers
        })

        connection.commit()

        # Fetch the DCR contacts for the department and location
        dcr_contacts = get_dcr_contacts(department, location)
        
        # Send email notifications
        send_email_notifications(dcr_contacts, emailid, name, allocatelicence, psno)
        
    except Exception as e:
        print(f"Error occurred: {e}")
        connection.rollback()
    finally:
        cursor.close()
    
    return redirect(url_for('dept', location=location, deptname=department))

@app.route('/insert_aa', methods=['POST'])# FORM FOR ADDITION OF NEW PRODUCTS & LOCATION
@auth.login_required
def insert_aa():
    location = request.form['location']
    department = request.form['dept']
    product = request.form['product']
    allocation = request.form['allocationLimit']

    cursor = connection.cursor()
    try:
        cursor.execute("""
            INSERT INTO LMSDEV.MASTER_ALLOCATION (LOCATION, DEPARTMENT, PRODUCT, ALLOCATION, ACTION_ON ) 
            VALUES (:location, :department, :product, :allocation, SYSDATE )
        """, {
            'location': location,
            'department': department,
            'product': product,
            'allocation': allocation
        })
        connection.commit()

        flash('Data inserted successfully', 'success')
    except cx_Oracle.DatabaseError as e:
        error, = e.args
        flash(f'Error occurred: {error.message}', 'error')
        connection.rollback()
    finally:
        cursor.close()

    return redirect(url_for('dept', location=location, deptname=department))


def get_dcr_contacts(department, location):
    cursor = connection.cursor()
    query_dcr = "SELECT EMAIL_ID FROM NUM_DCR WHERE DEPARTMENTS = :department AND location = :location"
    cursor.execute(query_dcr, {'department': department, 'location': location})
    dcr_contacts = [row[0] for row in cursor.fetchall()]
    cursor.close()
    return dcr_contacts

def send_email_notifications(dcr_contacts, user_email, user_name, product, psno):
    with app.app_context():
        #recipients = dcr_contacts + [user_email]
        recipients =[user_email]
        cc = dcr_contacts 
        print(recipients)
        print(cc)
        msg = Message(
            subject=f"Grant of {product} NUP License to {user_name}({psno}) on {date.today()}",
            sender=app.config['MAIL_DEFAULT_SENDER'],
            #recipients=recipients
            recipients= recipients,
            cc= cc,
            html=f"<p>Dear User,</p>"
                 f"<p></p>"  # Empty paragraph for blank line
                 f"<p>This is to inform you that you have been granted access of the <strong>{product}</strong> Named User License on <strong>{date.today()}.</strong></p>"
                 f"<p>For Installation/Unistallation kindly contact <a href=\"https://sim.lnthydrocarbon.com/\">SIM/Backoffice</a>.</p>"
                 f"<p>For any further assistance please contact your respective DCR.</p>"
                 f"<p></p>" 
                 f"<p>This is system generated e-mail. Please do not reply to this email</p>"
                 f"<p></p>" 
                 f"<p>Best Regards,<br>Named User Mgmt System(IT)</p>"
        )
        print(msg)
        mail.send(msg)

def send_revoke_notifications(dcr_contacts, user_email, user_name, product ,psno):
    try:
        with app.app_context():
            recipients = [user_email]
            cc= dcr_contacts
            print(recipients)
            print(cc) 
             # For debugging
            msg = Message(
                subject=f"Revoke of {product} NUP Licence to {user_name}({psno}) on {date.today()}",
                sender=app.config['MAIL_DEFAULT_SENDER'],
                recipients=recipients,
                cc=cc,
                html=f"<p>Dear User,</p>"
                        f"<p></p>"
                        f"<p>This is to inform you that you have been revoked access of the <strong>{product}</strong> Named User License on <strong>{date.today()}.</strong></p>"
                        f"<p>For Installation/Unistallation kindly contact <a href=\"https://sim.lnthydrocarbon.com/\">SIM/Backoffice</a>.</p>"
                        f"<p>For any further assistance please contact your respective DCR.</p>"
                        f"<p></p>"
                        f"<p>This is a system-generated email. Please do not reply to this email.</p>"
                        f"<p></p>"
                        f"<p>Best Regards,<br>Named User Mgmt System (IT Team)</p>"
            )
            print (msg)
            mail.send(msg)      
    except Exception as e:
        print(f"Error occurred while sending email: {e}")  # Log the error


@app.route('/access/<int:var>')
@auth.login_required
def access(var):
    cursor = connection.cursor()
    username = auth.username()
    query = "SELECT PSNO from NUMS_ADMIN where PSNO = :username"
    cursor.execute(query,{'username': username})
    admin_name = cursor.fetchall()
    psno = var
    if not psno:
        return "accessPsNo is required"

    session['psno'] = psno

    try:
        cursor.execute("""
            SELECT NAME, LOCATION, DEPT, EMAILID, LOADUSERS
            FROM "LMSDEV"."RLM" WHERE REVOKED_ON IS NULL AND  PSNO = :psno
        """, {'psno': psno})

        result = cursor.fetchone()

        if result:
            name, location, department, emailid, loadusers = result

            # Fetch products assigned to the PSNO
            cursor.execute("""
                SELECT PRODUCT
                FROM "LMSDEV"."RLM" WHERE REVOKED_ON IS NULL AND PSNO = :psno
            """, {'psno': psno})

            products_result = cursor.fetchall()
            products = [row[0] for row in products_result]

            return render_template('display.html', psno=psno, name=name, location=location, department=department,admin_name=admin_name, products=products, emailid=emailid, loadusers=loadusers)  # Added location=location
        else:
            return """
                <script>
                    alert('License has already been revoked!');
                    window.location.href = '{}';
                </script>
            """.format(url_for('dept', location=session.get('location'), deptname=session.get('deptname')))

    finally:
        cursor.close()


@app.route('/delete-product', methods=['POST'])
@auth.login_required
def delete_product():
    data = request.get_json()
    product = data.get('product')
    cursor = connection.cursor()
    

    if not product:
        return jsonify({'success': False, 'error': 'Product not found'}), 400

    psno = session.get('psno')
    if not psno:
        return jsonify({'success': False, 'error': 'PSNO not found in session'}), 400

    try:
        # Perform the update to mark the product as revoked
        cursor.execute("""
            UPDATE "LMSDEV"."RLM" SET REVOKED_ON = SYSDATE WHERE PSNO = :psno AND PRODUCT = :product
        """, {'psno': psno, 'product': product})
        connection.commit()

        # Fetch additional details needed for notification
        cursor.execute("""
            SELECT EMAILID, NAME, DEPT, LOCATION FROM "LMSDEV"."RLM" WHERE PSNO = :psno AND PRODUCT = :product
        """, {'psno': psno, 'product': product})
        result = cursor.fetchone()

        if result:
            emailid, name, department, location = result
            # Fetch DCR contacts for the department and location
            dcr_contacts = get_dcr_contacts(department, location)

            # Send notifications
            send_revoke_notifications(dcr_contacts, emailid, name, product,psno)

        return jsonify({'success': True}), 200

    except cx_Oracle.DatabaseError as e:
        error, = e.args
        connection.rollback()
        return jsonify({'success': False, 'error': str(error)}), 400

    finally:
        cursor.close()


@app.route('/log')
@auth.login_required
def showalldata():
    cursor = connection.cursor()
    location = session.get('location', 'Unknown')
    deptname = session.get('deptname', 'Unknown')
    username = auth.username()
    query = "SELECT PSNO from NUMS_ADMIN where PSNO = :username"
    cursor.execute(query,{'username': username})
    dept1=deptname
    print(dept1)
    admin_name = cursor.fetchall()
    columns = []
    data = []
    cursor = connection.cursor()
    if deptname.lower() == 'all' and admin_name:
        cursor.execute('''SELECT * FROM RLM WHERE LOCATION = :location ORDER BY GRANTED_ON DESC''', {'location': location})
    else:
        cursor.execute('''SELECT * FROM RLM WHERE LOCATION = :location AND DEPT = :deptname ORDER BY GRANTED_ON DESC''', {'location': location, 'deptname': deptname})
    
    data = cursor.fetchall()
    columns = [col[0] for col in cursor.description]
    cursor.close()
    return render_template('log.html', data=data, columns=columns,location=location)

@app.route('/addallocation')
@auth.login_required
def showalldata_aa():
    cursor = connection.cursor()
    location = session.get('location', 'Unknown')
    deptname = session.get('deptname', 'Unknown')
    columns = []
    data = []
    username = auth.username()
    query = "SELECT PSNO from NUMS_ADMIN where PSNO = :username"
    cursor.execute(query,{'username': username})
    admin_name = cursor.fetchall()
    
    try:
        if admin_name:
            cursor.execute('''SELECT * FROM master_allocation ORDER BY ACTION_ON DESC''')
        # else:
        #     cursor.execute('''SELECT * FROM master_allocation''')
        
        data = cursor.fetchall()
        columns = [col[0] for col in cursor.description]
    except cx_Oracle.DatabaseError as e:
        flash(f'Error occurred: {e}', 'error')
    finally:
        cursor.close()
    
    return render_template('addallocation.html', data=data, columns=columns, location=location, admin_name= admin_name,deptname=deptname)

@app.route('/delete-allocation/<location>/<department>/<product>', methods=['POST'])
@auth.login_required
def delete_allocation(location, department, product):
    cursor = connection.cursor()
    try:
        cursor.execute("""
            DELETE FROM LMSDEV.MASTER_ALLOCATION
            WHERE LOCATION = :location AND DEPARTMENT = :department AND PRODUCT = :product
        """, {
            'location': location,
            'department': department,
            'product': product
        })
        connection.commit()

        # # Call send_delete_notification after successful deletion
        # send_delete_notification(location, department, product)

        return jsonify({'success': True}), 200

    except cx_Oracle.DatabaseError as e:
        error, = e.args
        connection.rollback()
        return jsonify({'success': False, 'error': str(error)}), 400

    finally:
        cursor.close()

if __name__ == "__main__":
    app.run(host='192.168.44.121', debug=True , port=5000)
