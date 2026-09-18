from backend_database import connection
def load_history():
 with connection()as c:return[dict(x)for x in c.execute('SELECT * FROM performance_history')]
