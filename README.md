---

# 🚗 AAS-based Plug-and-Play Sensor System for Software-Defined Vehicles

## Overview

This repository contains a **complete prototype system** for **plug-and-play sensor integration** in **Software-Defined Vehicles (SDVs)** based on the **Asset Administration Shell (AAS)** concept.

The system demonstrates how standardized digital twins can be used to automatically identify, deploy, and activate heterogeneous sensors without manual configuration.
It is implemented and evaluated on an **Unmanned Ground Vehicle (UGV)** platform and follows a **distributed, three-component architecture**.

---

## System Architecture

The overall system consists of **three major subsystems**, each implemented as an independent module:

```text
.
├── oem_server/     # OEM cloud-side AAS repository and services
├── edge_device/    # Edge-side sensor ECU with bootstrap agent
├── ugv_system/     # Vehicle-side applications and middleware
└── README.md
```

Each subsystem represents a **distinct role in the plug-and-play workflow**.

---

## 1️⃣ OEM Server (`oem_server/`)

The OEM Server represents the **cloud-side backend** responsible for managing standardized sensor descriptions.

### Responsibilities

* Stores **AAS files** for supported sensors
* Provides AAS access via standardized interfaces
* Hosts references to:

  * Containerized sensor drivers
  * Containerized vehicle applications
* Validates AAS files using the official **AAS Test Engine**
* Acts as the authoritative source for sensor digital twins

### Role in Plug-and-Play

The OEM server enables **vendor-independent sensor integration** by providing machine-readable AAS descriptions that can be interpreted automatically by edge devices.

---

## 2️⃣ Edge Device (`edge_device/`)

The Edge Device is implemented on a **Raspberry Pi** and acts as a **Sensor ECU**.

### Core Component: Bootstrap Agent

The edge device runs a **Bootstrap Agent** responsible for orchestrating the entire plug-and-play process.

### Responsibilities

* Detects newly connected hardware (e.g., USB hot-plug)
* Extracts hardware identifiers
* Queries the OEM server for matching AAS files
* Retrieves and validates AAS metadata
* Pulls and launches containerized **driver images**
* Exposes sensor services and AAS endpoints
* Advertises services within the local network

### Role in Plug-and-Play

The edge device **abstracts raw sensor data** and eliminates manual driver installation and configuration, enabling configuration-free deployment.

---

## 3️⃣ UGV System (`ugv_system/`)

The UGV System represents the **vehicle-side runtime environment**.

### Responsibilities

* Runs vehicle applications and middleware
* Consumes abstracted sensor data via standardized APIs
* Interacts with sensors without hardware-specific knowledge
* Implements perception, monitoring, or control functions

### Role in Plug-and-Play

Vehicle applications can immediately use newly connected sensors **without modification**, demonstrating the decoupling of software from hardware.

---

## Plug-and-Play Workflow (End-to-End)

1. A sensor is physically connected to the edge device
2. The Bootstrap Agent detects the sensor and reads its identifier
3. The edge device queries the OEM server for a matching AAS
4. The AAS file is retrieved and validated
5. Driver and application container images referenced in the AAS are pulled
6. Containers are started automatically
7. The sensor becomes immediately usable by the UGV system

The entire process completes within a few seconds and requires no manual configuration.

---

## Key Design Principles

* **Standardized Digital Twins** using AAS
* **Hardware–Software Decoupling**
* **Containerized Drivers and Applications**
* **Automatic Deployment via Metadata**
* **Scalability and Reusability**
* **Reproducibility for Research**

---

## Evaluation Summary

The system has been evaluated using multiple USB-based sensors, including cameras and ultrasonic sensors.
Experimental results show that newly connected sensors become operational within approximately **two seconds**, validating the feasibility of the proposed approach.

Detailed evaluation results are described in the corresponding master’s thesis.

---

## Repository Usage

Each subsystem contains its own documentation and setup instructions:

```text
oem_server/README.md
edge_device/README.md
ugv_system/README.md
```

Please refer to these files for deployment and execution details.

---

## Limitations

* Current prototype focuses on USB-based sensors
* Advanced automotive buses (CAN, LIN, FlexRay) are not yet supported
* Service discovery mechanisms may be restricted in managed networks

---

## Context

This project is developed as part of a **master’s thesis** on **AAS-based hardware abstraction for plug-and-play sensor systems in Software-Defined Vehicles**.

---
