"""SQLite repository and deterministic hackathon seed for AURA."""
import os, json, tempfile, shutil, random, sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

_firebase_client = None

def get_firestore():
    global _firebase_client
    if _firebase_client is not None:
        return _firebase_client
    try:
        import firebase_admin
        from firebase_admin import credentials, firestore
        if not firebase_admin._apps:
            cred_env = os.environ.get("FIREBASE_CREDENTIALS")
            if cred_env:
                cred_dict = json.loads(cred_env)
                cred = credentials.Certificate(cred_dict)
            elif os.path.exists("serviceAccountKey.json"):
                cred = credentials.Certificate("serviceAccountKey.json")
            else:
                return None
            firebase_admin.initialize_app(cred)
        _firebase_client = firestore.client()
        return _firebase_client
    except Exception as e:
        print(f"Firebase init notice: {e}")
        return None

def sync_event_to_firebase(collection_name: str, doc_id: str, data: dict):
    db = get_firestore()
    if db:
        try:
            db.collection(collection_name).document(doc_id).set(data, merge=True)
        except Exception as e:
            print(f"Firestore sync error on {collection_name}/{doc_id}: {e}")

def _get_db_path():
    base_db = Path(__file__).with_name("aura.db")
    if os.environ.get("VERCEL") or not os.access(Path(__file__).parent, os.W_OK):
        tmp_db = Path(tempfile.gettempdir()) / "aura.db"
        if not tmp_db.exists() and base_db.exists():
            try:
                shutil.copy(base_db, tmp_db)
            except Exception:
                pass
        return tmp_db if tmp_db.exists() else base_db
    return base_db

DATABASE_PATH=_get_db_path()
SKILLS=["Python","Java","JavaScript","React","FastAPI","SQL","Machine Learning","Deep Learning","NLP","Computer Vision","Cloud","DevOps","Docker","Cybersecurity","Data Engineering","Data Analysis","UI/UX","Testing","Project Management","System Design"]
ROLES=[("Backend Engineer",["Python","FastAPI","SQL","Docker","System Design"]),("Data Engineer",["Python","SQL","Data Engineering","Cloud","Docker"]),("Frontend Engineer",["JavaScript","React","UI/UX","Testing","System Design"]),("DevOps Engineer",["Cloud","DevOps","Docker","Cybersecurity","Python"]),("AI Engineer",["Python","Machine Learning","NLP","Deep Learning","Cloud"]),("Data Analyst",["SQL","Data Analysis","Python","Project Management","Testing"])]
NAMES=["Arun Kumar","Priya Nair","Rahul Mehta","Nikhil Shah","Maya Iyer","Vikram Rao","Aditi Singh","Karan Patel","Sneha Gupta","Arjun Das"]
@contextmanager
def connection():
 c=sqlite3.connect(DATABASE_PATH);c.row_factory=sqlite3.Row;c.execute("PRAGMA foreign_keys=ON")
 try: yield c;c.commit()
 finally:c.close()
def sync_all_to_firebase():
    db = get_firestore()
    if not db:
        return
    try:
        with connection() as c:
            emp_ref = db.collection("employees")
            if not len(list(emp_ref.limit(1).stream())):
                for emp in c.execute("SELECT * FROM employees"):
                    emp_dict = dict(emp)
                    emp_ref.document(emp_dict["employee_id"]).set(emp_dict)
            task_ref = db.collection("tasks")
            if not len(list(task_ref.limit(1).stream())):
                for t in c.execute("SELECT * FROM tasks"):
                    t_dict = dict(t)
                    task_ref.document(t_dict["task_id"]).set(t_dict)
    except Exception as e:
        print(f"Initial Firestore sync error: {e}")

def initialise_database():
 with connection() as c:
  c.executescript('''CREATE TABLE IF NOT EXISTS employees (employee_id TEXT PRIMARY KEY,name TEXT NOT NULL,department TEXT NOT NULL,job_role TEXT NOT NULL,location TEXT NOT NULL,status TEXT NOT NULL,availability INTEGER NOT NULL,daily_capacity_hours REAL NOT NULL,current_workload_hours REAL NOT NULL,utilization_percentage REAL NOT NULL,hourly_cost_inr REAL NOT NULL,performance_rating REAL NOT NULL,sla_success_rate REAL NOT NULL,average_task_completion_hours REAL NOT NULL,years_experience INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS skills (skill_id TEXT PRIMARY KEY,name TEXT UNIQUE NOT NULL);CREATE TABLE IF NOT EXISTS employee_skills (employee_id TEXT REFERENCES employees(employee_id),skill_id TEXT REFERENCES skills(skill_id),level INTEGER NOT NULL CHECK(level BETWEEN 1 AND 5),PRIMARY KEY(employee_id,skill_id));CREATE TABLE IF NOT EXISTS tasks (task_id TEXT PRIMARY KEY,task_name TEXT NOT NULL,description TEXT NOT NULL,department TEXT NOT NULL,priority TEXT NOT NULL,status TEXT NOT NULL,deadline TEXT NOT NULL,estimated_hours REAL NOT NULL,remaining_hours REAL NOT NULL,revenue_inr REAL NOT NULL,sla_penalty_inr REAL NOT NULL,complexity INTEGER NOT NULL);CREATE TABLE IF NOT EXISTS task_requirements (task_id TEXT REFERENCES tasks(task_id),skill_id TEXT REFERENCES skills(skill_id),required_level INTEGER NOT NULL,PRIMARY KEY(task_id,skill_id));CREATE TABLE IF NOT EXISTS assignments (assignment_id TEXT PRIMARY KEY,employee_id TEXT REFERENCES employees(employee_id),task_id TEXT REFERENCES tasks(task_id),allocated_hours REAL NOT NULL,status TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS performance_history (record_id INTEGER PRIMARY KEY AUTOINCREMENT,employee_id TEXT REFERENCES employees(employee_id),task_id TEXT REFERENCES tasks(task_id),completion_hours REAL NOT NULL,sla_met INTEGER NOT NULL,recorded_at TEXT NOT NULL);CREATE TABLE IF NOT EXISTS leave_requests (leave_id TEXT PRIMARY KEY,employee_id TEXT REFERENCES employees(employee_id),start_date TEXT NOT NULL,end_date TEXT NOT NULL,status TEXT NOT NULL);CREATE TABLE IF NOT EXISTS break_sessions (break_id TEXT PRIMARY KEY,employee_id TEXT REFERENCES employees(employee_id),break_type TEXT NOT NULL,status TEXT NOT NULL,started_at TEXT NOT NULL,ended_at TEXT);CREATE TABLE IF NOT EXISTS events (event_id TEXT PRIMARY KEY,event_type TEXT NOT NULL,employee_id TEXT,task_id TEXT,payload_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS simulation_runs (run_id TEXT PRIMARY KEY,scenario_type TEXT NOT NULL,input_json TEXT NOT NULL,result_json TEXT NOT NULL,created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);CREATE TABLE IF NOT EXISTS notifications (notification_id TEXT PRIMARY KEY,message TEXT NOT NULL,severity TEXT NOT NULL,read_at TEXT);CREATE TABLE IF NOT EXISTS recommendations (recommendation_id TEXT PRIMARY KEY,task_id TEXT NOT NULL,employee_id TEXT NOT NULL,before_risk REAL,after_risk REAL,explanation_json TEXT NOT NULL,status TEXT NOT NULL DEFAULT 'PENDING',created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP);''')
  if not c.execute("SELECT COUNT(*) FROM employees").fetchone()[0]:
   seed(c)
  sync_all_to_firebase()
def reset_database():
 """Restore the demo to its deterministic initial state."""
 if DATABASE_PATH.exists(): DATABASE_PATH.unlink()
 initialise_database()
def seed(c):
 rng=random.Random(42);now=datetime.now(timezone.utc);c.executemany("INSERT INTO skills VALUES (?,?)",[(f"S{i:03}",n)for i,n in enumerate(SKILLS,1)])
 for i in range(1,51):
  role,core=ROLES[(i-1)%6];name=NAMES[(i-1)%10]+(""if i<=10 else f" {i}");work=round(rng.uniform(1.5,7.5),1);status="AVAILABLE"if i not in(1,3)else("ON_BREAK"if i==1 else"WORKING")
  c.execute("INSERT INTO employees VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",(f"E{i:03}",name,role.split()[0]+" Delivery",role,["Chennai","Bengaluru","Mumbai","Pune"][i%4],status,status=="AVAILABLE",8,work,round(work/8*100,1),rng.randrange(700,1600),round(rng.uniform(3.3,4.9),2),round(rng.uniform(82,99),1),round(rng.uniform(4,15),1),rng.randrange(1,12)))
  for s in list(dict.fromkeys(core+rng.sample(SKILLS,3)))[:rng.randint(4,8)]:c.execute("INSERT INTO employee_skills VALUES (?,?,?)",(f"E{i:03}",f"S{SKILLS.index(s)+1:03}",rng.randint(3,5)if s in core else rng.randint(1,4)))
 for i in range(1,101):
  tid=f"T-{100+i:03}";role,core=ROLES[(i-1)%6];p="Critical"if i in(1,30)else("High"if i%5==0 else"Medium");h=round(rng.uniform(3,18),1);status="UNASSIGNED"if i==1 else"ACTIVE"
  c.execute("INSERT INTO tasks VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",(tid,"Production login outage"if i==1 else f"{role} delivery #{i}",f"Synthetic operational task {i}.",role.split()[0]+" Delivery",p,status,(now+timedelta(hours=2+i%72)).isoformat(),h,h,rng.randrange(50000,500001),rng.randrange(5000,50001),rng.randint(1,5)))
  for s in rng.sample(core,rng.randint(1,4)):c.execute("INSERT INTO task_requirements VALUES (?,?,?)",(tid,f"S{SKILLS.index(s)+1:03}",rng.randint(2,4)))
  if i!=1:c.execute("INSERT INTO assignments(assignment_id,employee_id,task_id,allocated_hours,status) VALUES (?,?,?,?,?)",(f"A{i:03}",f"E{((i-1)%50)+1:03}",tid,round(h*.7,1),"ACTIVE"))
 for i in range(1000):c.execute("INSERT INTO performance_history(employee_id,task_id,completion_hours,sla_met,recorded_at) VALUES (?,?,?,?,?)",(f"E{(i%50)+1:03}",f"T-{101+i%100:03}",round((6+i%12)*rng.uniform(.65,1.35),2),rng.random()>.12,(now-timedelta(days=i%365)).isoformat()))
 c.execute("INSERT INTO break_sessions VALUES (?,?,?,?,?,?)",("B001","E001","MEAL_BREAK","ACTIVE",(now-timedelta(minutes=47)).isoformat(),None))
