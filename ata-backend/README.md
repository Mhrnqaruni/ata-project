# ATA Backend

This is the backend for the AI Teaching Assistant platform.

## Database Migrations

This project uses Alembic to manage database migrations. To apply the latest migrations, run the following command from within the `ata-backend` directory:

```bash
alembic upgrade head
```

**Note:** Before running the migration, ensure you have a `.env` file in this directory with a valid `DATABASE_URL` connection string. See `.env.example` for the required format.

## Running the Application

To run the application locally, first install the dependencies:

```bash
pip install -r requirements.txt
```

Then, start the server using uvicorn:

```bash
uvicorn app.main:app --reload
```