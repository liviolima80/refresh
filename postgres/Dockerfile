# Use the official PostgreSQL image
FROM postgres:18.1

# Set environment variables (Optional: strictly speaking, you can pass these at runtime)
# generally it is better to set secrets via command line or .env files, 
# but for a self-contained image, this works.
ENV POSTGRES_DB=refresh
ENV POSTGRES_USER=postgres
ENV POSTGRES_PASSWORD=sQl2025!

# Copy the SQL script into the initialization directory
COPY init.sql /docker-entrypoint-initdb.d/
