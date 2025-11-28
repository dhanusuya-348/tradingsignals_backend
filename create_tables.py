from dotenv import load_dotenv
load_dotenv()  # Load .env file

from models import Base, engine

def create_all_tables():
    print("Creating tables...")
    Base.metadata.create_all(engine)
    print("✅ All tables created successfully!")

if __name__ == "__main__":
    create_all_tables()