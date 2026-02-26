from shared.db import Session, Table, Base, engine

# Спочатку скидаємо старі таблиці
Base.metadata.drop_all(engine, tables=[
    Base.metadata.tables.get('reservation'),
    Base.metadata.tables.get('tables'),
])
Base.metadata.create_all(engine)

tables_data = [
    # Тип 1-2 (10 столиків) — вздовж лівої стіни
    {"number": 1,  "type": "1-2", "label": "Біля вікна",  "x": 10, "y": 15},
    {"number": 2,  "type": "1-2", "label": "Біля вікна",  "x": 10, "y": 28},
    {"number": 3,  "type": "1-2", "label": "Біля вікна",  "x": 10, "y": 41},
    {"number": 4,  "type": "1-2", "label": "Біля вікна",  "x": 10, "y": 54},
    {"number": 5,  "type": "1-2", "label": "Біля вікна",  "x": 10, "y": 67},
    {"number": 6,  "type": "1-2", "label": "Кут",         "x": 10, "y": 80},
    {"number": 7,  "type": "1-2", "label": "Центр",       "x": 25, "y": 20},
    {"number": 8,  "type": "1-2", "label": "Центр",       "x": 25, "y": 40},
    {"number": 9,  "type": "1-2", "label": "Центр",       "x": 25, "y": 60},
    {"number": 10, "type": "1-2", "label": "Центр",       "x": 25, "y": 80},
    # Тип 3-4 (8 столиків) — центр залу
    {"number": 11, "type": "3-4", "label": "Центр",       "x": 45, "y": 20},
    {"number": 12, "type": "3-4", "label": "Центр",       "x": 45, "y": 38},
    {"number": 13, "type": "3-4", "label": "Центр",       "x": 45, "y": 56},
    {"number": 14, "type": "3-4", "label": "Центр",       "x": 45, "y": 74},
    {"number": 15, "type": "3-4", "label": "Центр",       "x": 60, "y": 20},
    {"number": 16, "type": "3-4", "label": "Центр",       "x": 60, "y": 38},
    {"number": 17, "type": "3-4", "label": "Центр",       "x": 60, "y": 56},
    {"number": 18, "type": "3-4", "label": "Центр",       "x": 60, "y": 74},
    # Тип 4+ (4 столики) — права сторона, VIP
    {"number": 19, "type": "4+",  "label": "VIP",         "x": 80, "y": 22},
    {"number": 20, "type": "4+",  "label": "VIP",         "x": 80, "y": 45},
    {"number": 21, "type": "4+",  "label": "VIP",         "x": 80, "y": 65},
    {"number": 22, "type": "4+",  "label": "VIP-Кут",     "x": 80, "y": 83},
]

with Session() as cursor:
    for t in tables_data:
        cursor.add(Table(
            number=t["number"],
            type_table=t["type"],
            label=t["label"],
            x=t["x"],
            y=t["y"]
        ))
    cursor.commit()
    print(f"✅ Додано {len(tables_data)} столиків!")