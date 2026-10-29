import sqlite3, random
from faker import Faker
fake = Faker(); Faker.seed(11); random.seed(11)
db = sqlite3.connect("data/users.db")
db.execute("DROP TABLE IF EXISTS users")
db.execute("CREATE TABLE users (student_id TEXT PRIMARY KEY, name TEXT, email TEXT, phone TEXT, dob TEXT, gpa REAL)")
for _ in range(200):
    sid = f"S{random.randint(10000000, 99999999)}"
    db.execute("INSERT INTO users VALUES (?,?,?,?,?,?)",
        (sid, fake.name(), f"{sid.lower()}@lab.test", fake.phone_number(),
        fake.date_of_birth(minimum_age=18, maximum_age=30).isoformat(), 
round(random.uniform(2.0, 4.0), 2)))
db.execute("INSERT OR REPLACE INTO users VALUES ('S00000001','Canary Person','canary-pii91c2@lab.test','555-0100','2000-01-01',4.0)")
db.commit(); print("users:", db.execute("select count(*) from users").fetchone()[0])
