## Docker Compose Instructions

> [!IMPORTANT]  
> All commands must be executed from root.

* `docker compose -f docker/docker-compose.yml run --rm samowarium-container python samowarium.py` - build and run container
* `docker compose -f docker/docker-compose.yml down -v` - stop and remove container
* `docker compose -f docker/docker-compose.yml build` - rebuild base image
