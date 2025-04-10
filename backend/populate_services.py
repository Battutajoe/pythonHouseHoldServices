import os
import json
from models import db, Service
import logging

# Configure logging
logger = logging.getLogger('app')
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def load_services_from_file(file_path):
    """Load services from a JSON file."""
    try:
        with open(file_path, "r", encoding='utf-8') as f:
            services = json.load(f)
        logger.info(f"✅ Successfully loaded services from {file_path}")
        return services
    except FileNotFoundError:
        logger.error(f"❌ File not found: {file_path}")
        raise
    except json.JSONDecodeError as e:
        logger.error(f"❌ Invalid JSON in file {file_path}: {str(e)}")
        raise
    except Exception as e:
        logger.error(f"❌ Error loading services from file: {str(e)}")
        raise

def validate_service_data(service_data):
    """Validate service data before processing."""
    required_fields = ["category", "name", "price"]
    for field in required_fields:
        if field not in service_data:
            raise ValueError(f"Missing required field: {field}")
    if not isinstance(service_data["name"], str) or not service_data["name"].strip():
        raise ValueError("Service name must be a non-empty string")
    if not isinstance(service_data["price"], (int, float)) or service_data["price"] < 0:
        raise ValueError("Price must be a non-negative number")
    return True

def process_services(services_data, existing_services):
    """Process services data and prepare for database operations."""
    new_services = []
    updated_services = []

    for service_data in services_data:
        try:
            # Validate service data
            validate_service_data(service_data)

            # Create a Service object
            service = Service(
                category=service_data["category"],
                name=service_data["name"],
                price=service_data["price"],
                currency=service_data.get("currency", "KES"),
                description=service_data.get("description", ""),
                is_active=service_data.get("is_active", True)
            )

            # Check if the service already exists
            existing = existing_services.get(service_data["name"])
            if not existing:
                new_services.append(service)
                logger.info(f"✅ New service added: {service_data['name']}")
            else:
                # Update existing service if there are changes
                if (
                    existing.category != service_data["category"] or
                    existing.price != service_data["price"] or
                    existing.currency != service_data.get("currency", "KES") or
                    existing.description != service_data.get("description", "") or
                    existing.is_active != service_data.get("is_active", True)
                ):
                    existing.category = service_data["category"]
                    existing.price = service_data["price"]
                    existing.currency = service_data.get("currency", "KES")
                    existing.description = service_data.get("description", "")
                    existing.is_active = service_data.get("is_active", True)
                    updated_services.append(existing)
                    logger.info(f"✅ Service updated: {service_data['name']}")

        except ValueError as e:
            logger.warning(f"❌ Invalid service data: {service_data}. Error: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Unexpected error processing service data: {service_data}. Error: {str(e)}")

    return new_services, updated_services

def populate_services(app):
    """Populate the Service table with predefined services from a JSON file."""
    file_path = os.path.join(os.path.dirname(__file__), "services.json")
    if not os.path.exists(file_path):
        logger.error(f"❌ File not found: {file_path}")
        return

    # Load services data from the JSON file
    services_data = load_services_from_file(file_path)

    with app.app_context():
        try:
            # Ensure the database tables are created
            db.create_all()

            # Fetch existing services for comparison
            existing_services = {service.name: service for service in Service.query.all()}

            # Process services data
            new_services, updated_services = process_services(services_data, existing_services)

            # Add new services to the database
            if new_services:
                db.session.bulk_save_objects(new_services)
                logger.info(f"✅ {len(new_services)} new services added successfully!")

            # Update existing services in the database
            if updated_services:
                db.session.add_all(updated_services)
                logger.info(f"✅ {len(updated_services)} services updated successfully!")

            # Commit the transaction
            db.session.commit()

            if not new_services and not updated_services:
                logger.info("✅ No new or updated services to process. Database is up to date.")

        except Exception as e:
            # Rollback the transaction in case of an error
            db.session.rollback()
            logger.error(f"❌ Error processing services: {str(e)}")
            raise
        finally:
            # Close the database session
            db.session.close()

if __name__ == "__main__":
    from app import create_app
    app = create_app()
    populate_services(app)