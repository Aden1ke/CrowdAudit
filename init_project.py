import os

folders = ["ingestion", "scoring", "api", "zerve_prompts", "benchmarks", "tests"]


def scaffold():
    for folder in folders:
        if not os.path.exists(folder):
            os.makedirs(folder)
            with open(os.path.join(folder, "__init__.py"), "w") as f:
                pass  # Makes Python treat folders as packages
            print(f"✔ Created {folder}/")

    if not os.path.exists(".env"):
        print("⚠ Reminder: Create your .env file based on .env.example")


if __name__ == "__main__":
    scaffold()
