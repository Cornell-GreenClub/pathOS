# pathOS Backend Guide: Local vs. Production

This document outlines how the **pathOS** backend architecture connects, and how to start the resources locally for development versus how they're run in production.

## Architecture Refresher
The pathOS routing engine requires three active pieces linking together:
1. **The Next.js Frontend** (User Interface)
2. **The Flask Backend** (Optimization Logic)
3. **The OSRM Engine** (Routing & Geometry Generation)

---

## Local Development Environment

When doing development locally, all three services run directly on your machine. This avoids incurring cloud costs and gives you faster debug cycles.

### 1. The OSRM Routing Engine (Local Docker)
The Flask backend expects to talk to a local OSRM instance. First, you need the route data loaded into a Docker container.

Please refer to the **OSRM New York Setup Guide** at the bottom of this document for full instructions on downloading the data and starting the container.

### 2. The Flask Backend (Local Python App)
Next, spin up the optimization server that coordinates the routing math.

```bash
cd backend
source venv/bin/activate
python3 app/app.py
```
*Note: This spins up the local backend at `http://localhost:8000`. To stop the server when you are done, press `Ctrl+C` in your terminal.*

> **IMPORTANT (.env Routing):** By default, if your root `.env` file contains `OSRM_WAKE_URL` and `OSRM_WAKE_SECRET`, your local backend will trigger the AWS Lambda and boot your actual AWS cloud server for testing. Unless this is intended for your specific testing, simply `# comment out` those two lines in your `.env` file

### 3. The Next.js Frontend (Local Dev Server)
When you run `npm run dev`, your local Next.js frontend is configured inside `page.tsx` to target your local variables:
* **Backend:** `http://localhost:8000/optimize_route`
* **OSRM:** `http://127.0.0.1:5000/route/v1/...`

---

## Production Deployment Environment

In production, all three systems are decoupled and hosted on different cloud providers to ensure the site is globally accessible.
* **Frontend:** Deployed to Vercel
* **Backend:** Deployed to Render.com
* **OSRM Server:** Deployed to an AWS EC2 instance

### 1. The OSRM Server (AWS EC2 - Auto Hibernating)
Due to memory requirements for processing the full New York State roadmap, this is hosted on an **AWS EC2 `t3.large` instance**. 
* **Dynamic IP Setup:** To slash costs, this server is configured to safely Auto-Hibernate when inactive, dropping its IP address entirely to negate AWS IP fees. When a user requests a route, the pathOS Render backend dynamically hits an AWS Lambda securely (`OSRM_WAKE_URL`), which intelligently boots the server and returns the fresh IP address on the fly. 
*(See `osrm_aws_deployment_guide.md` for the extensive AWS architectural setup).*

### 2. The Flask Backend (Render)
The pathOS Python logic is pushed to a **free-tier instance on Render**. 
* **URL:** `https://asphalt-backend.onrender.com`

*Note: Render's free tier spins down after inactivity. The pathOS frontend triggers a "warm-up" `GET /health` call to this URL when a user lands on the site so the server has time to boot up before they hit "Optimize Route".*

### 3. The Next.js Frontend (Vercel)
When your project is built with `npm run build` or pushed to Vercel, Next.js utilizes the `.env.production` file. This rewrites the frontend to interact with the live AWS and Render servers instead of looking at your local machine.

---

## OSRM New York Setup Guide

This documentation provides a streamlined workflow for deploying a local instance of the **Open Source Routing Machine (OSRM)** using New York State data.

**Reference:** [Project-OSRM/osrm-backend GitHub](https://github.com/Project-OSRM/osrm-backend)

### 1. Prerequisites
- **Docker Desktop:** Ensure it is installed and the engine is running.
- **Disk Space:** ~5GB recommended for New York processing.
- **Terminal:** You should be inside your `osrm-ny` directory. Create this folder at the same level in your project file structure as /frontend, /backend, and /archive.

### 2. Download Map Data
Using `curl` to download the latest New York State extract from Geofabrik.

```bash
curl -L -O http://download.geofabrik.de/north-america/us/new-york-latest.osm.pbf
```

### 3. Data Processing Pipeline
OSRM requires a three-step pre-processing sequence before the server can handle requests.

#### Step 1: Extract
Extracts the routing graph from the OSM data using the default car profile.
```bash
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-extract -p /opt/car.lua /data/new-york-latest.osm.pbf
```

#### Step 2: Partition
Partitions the graph into cells for the Multi-Level Dijkstra (MLD) algorithm.
```bash
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-partition /data/new-york-latest.osrm
```

#### Step 3: Customize
Calculates travel times and weights based on the routing profile.
```bash
docker run -t -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-customize /data/new-york-latest.osrm
```

### 4. Run the Routing Server
Start the HTTP server on port 5000. This `run` command creates the container from scratch and runs it in the background (`-d`). 

**Note: You only need to run this giant command the very first time you set it up.**
```bash
docker run -d --name osrm-ny -p 5000:5000 -v "${PWD}:/data" ghcr.io/project-osrm/osrm-backend osrm-routed --algorithm mld /data/new-york-latest.osrm
```

If you have already created the container and just need to start your paused server again for development, simply use:
```bash
docker start osrm-ny
```

### 5. Usage & Testing
You can now send HTTP requests to your local server.

Check if the server is up:
```bash
curl "http://localhost:5000/nearest/v1/driving/-73.9851,40.7588"
```

Get a route (Times Square to Empire State Building):
```bash
curl "http://localhost:5000/route/v1/driving/-73.9851,40.7588;-73.9857,40.7484?steps=true"
```

### 6. Maintenance Commands

| Task | Command |
| :--- | :--- |
| View Logs | `docker logs -f osrm-ny` |
| Stop Server | `docker stop osrm-ny` |
| Start Server | `docker start osrm-ny` |
| Remove Server | `docker rm -f osrm-ny` |