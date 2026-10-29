import random, pathlib
from faker import Faker
fake = Faker(); Faker.seed(7); random.seed(7)
out = pathlib.Path("data/corpus")
buildings = ["Bell Tower", "Broome Library", "Sierra Hall", "Aliso Hall", "Del Norte"]
for i in range(36):
    b = random.choice(buildings)
    (out / f"lab_{i:02d}.md").write_text(f"""# Computer Lab Notice {i:02d}: {b}

## Hours
Open {random.randint(7,9)}:00 to {random.randint(18,22)}:00 on weekdays.

## Contact
Lab lead: {fake.name()}, extension x{random.randint(1000,9999)}.

## Equipment
{random.randint(10,40)} workstations; printer queue name `{b.split()[0].lower()}-prn-{i:02d}`.
""")

print("corpus files:", len(list(out.glob('*.md'))))
