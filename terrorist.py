import sqlite3
import os

DB_PATH = "terrorist.db"

# ─────────────────────────────────────────
#  CREATE TABLES
# ─────────────────────────────────────────
def create_tables(cur):
    cur.executescript("""
        CREATE TABLE IF NOT EXISTS persons (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT NOT NULL UNIQUE,
            date_of_birth   TEXT,
            date_of_death   TEXT,
            status          TEXT,
            created_at      DATETIME DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS activities (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id   INTEGER NOT NULL,
            activity    TEXT NOT NULL,
            FOREIGN KEY (person_id) REFERENCES persons(id)
        );
    """)


# ─────────────────────────────────────────
#  ADD A PERSON
# ─────────────────────────────────────────
def add_person(cur, name, date_of_birth, date_of_death, status, activities: list):
    """
    date_of_birth / date_of_death: use "YYYY-MM-DD" format or None
    status: e.g. "Active (Fugitive)" or "Not Active (Killed)"
    activities: list of strings, one per bullet point
    """
    cur.execute("""
        INSERT INTO persons (name, date_of_birth, date_of_death, status)
        VALUES (?, ?, ?, ?)
    """, (name, date_of_birth, date_of_death, status))

    person_id = cur.lastrowid

    for act in activities:
        cur.execute(
            "INSERT INTO activities (person_id, activity) VALUES (?, ?)",
            (person_id, act.strip())
        )

    print(f"  ✅  Added: {name}")


# ─────────────────────────────────────────
#  SEED DATA  ← add your people here
# ─────────────────────────────────────────
PEOPLE = [
    {
        "name"          : "Osama bin Laden",
        "date_of_birth" : "1957-03-10",
        "date_of_death" : "2011-05-02",
        "status"        : "Not Active (Killed)",
        "activities"    : [
            "Founder of Al-Qaeda (1988), transforming it into a global jihadist network",
            "Financed and organized militant training camps in Afghanistan and Sudan",
            "Issued multiple fatwas against the United States, calling for global jihad",
            "Mastermind behind the September 11 attacks",
            "Linked to 1998 U.S. Embassy bombings in Kenya and Tanzania",
            "Coordinated attacks like the USS Cole bombing (2000)",
            "Played a central ideological and financial role in global terrorism until killed in 2011",
        ],
    },
    {
        "name"          : "dawood_ibrahim",
        "date_of_birth" : "1955-12-26",
        "date_of_death" : None,
        "status"        : "Active (Fugitive)",
        "activities"    : [
            "Founder of D-Company, a transnational organized crime syndicate",
            "Mastermind of the 1993 Bombay bombings",
            "Built a network involving drug trafficking, extortion, arms smuggling, and money laundering",
            "Maintained links with terrorist organizations and intelligence networks",
            "Expanded operations across South Asia, Middle East, and Africa",
            "Remains one of India's most wanted fugitives",
        ],
    },

    # ── ADD MORE PEOPLE BELOW ──
    # {
    #     "name"          : "Full Name",
    #     "date_of_birth" : "YYYY-MM-DD",   # or None
    #     "date_of_death" : None,            # or "YYYY-MM-DD"
    #     "status"        : "Active (Fugitive)",
    #     "activities"    : [
    #         "First activity description",
    #         "Second activity description",
    #     ],
    # },
]


# ─────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────
def main():
    already_exists = os.path.exists(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur  = conn.cursor()

    create_tables(cur)

    if already_exists:
        print(f"📂  '{DB_PATH}' already exists — adding only new records.\n")
    else:
        print(f"🆕  Creating '{DB_PATH}'...\n")

    added = 0
    for person in PEOPLE:
        # Skip if already in DB (unique name constraint)
        cur.execute("SELECT id FROM persons WHERE name = ?", (person["name"],))
        if cur.fetchone():
            print(f"  ⏭   Skipped (already exists): {person['name']}")
            continue

        add_person(
            cur,
            name          = person["name"],
            date_of_birth = person["date_of_birth"],
            date_of_death = person["date_of_death"],
            status        = person["status"],
            activities    = person["activities"],
        )
        added += 1

    conn.commit()

    # ── Summary ──
    total_persons    = cur.execute("SELECT COUNT(*) FROM persons").fetchone()[0]
    total_activities = cur.execute("SELECT COUNT(*) FROM activities").fetchone()[0]
    conn.close()

    print(f"\n{'─'*45}")
    print(f"  Added this run : {added} person(s)")
    print(f"  Total persons  : {total_persons}")
    print(f"  Total activities: {total_activities}")
    print(f"  Database        : {DB_PATH}")
    print(f"{'─'*45}")
    print(f"\n✅  Done.")


if __name__ == "__main__":
    main()