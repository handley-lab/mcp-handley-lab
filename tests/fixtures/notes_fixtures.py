"""
Test fixtures for notes integration tests.

This module provides realistic mock data that represents a research lab's
knowledge management system with interconnected notes.
"""

from datetime import datetime

from mcp_handley_lab.notes.models import Note


def get_test_notes_data():
    """
    Get comprehensive test data representing a research lab's notes.

    Returns interconnected notes across multiple types:
    - People (researchers, collaborators)
    - Projects (active research)
    - Papers (publications)
    - Grants (funding)
    - Equipment (shared resources)
    - Ideas (research concepts)
    - Meetings (collaboration records)
    """

    # Generate consistent UUIDs for cross-references
    person_ids = {
        "sarah_chen": "cbd05128-c5f2-4642-9e11-54b46eef4c8e",
        "prof_johnson": "320bd1c6-850f-4bbf-917e-ff7050723172",
        "alex_kim": "792b6ce9-0260-4c53-a008-884b691ea015",
        "dr_martinez": "b8e4d2c1-3f7a-4b9e-8c6d-1a2b3c4d5e6f",
    }

    project_ids = {
        "neural_odes": "9ea1e787-78f2-45e8-8b33-8df0e130beb8",
        "genomics_pipeline": "4acbb6e9-f777-4699-94de-3ea39f1e146a",
        "graph_networks": "2a74494f-ab7f-41d4-9c91-2bf4430c2e3b",
    }

    paper_ids = {
        "neural_odes_nature": "ac82e618-d60b-44d5-a7ea-04bb5a8092b1",
        "genomics_mlsys": "00f30024-391e-451f-9f48-092702ed8595",
        "climate_review": "fe123456-789a-bcde-f012-3456789abcde",
    }

    grant_ids = {"nsf_climate": "da2f1400-fc96-42eb-abea-3ffe81bcafbc"}

    equipment_ids = {"gpu_cluster": "fd41f4e6-0189-4bdc-8821-697bba780a02"}

    base_time = datetime(2025, 7, 6, 16, 14, 0)

    notes = [
        # People
        Note(
            id=person_ids["sarah_chen"],
            type="person",
            properties={
                "name": "Dr. Sarah Chen",
                "role": "Principal Investigator",
                "department": "Computational Biology",
                "email": "s.chen@university.edu",
                "expertise": ["machine learning", "genomics", "bioinformatics"],
            },
            tags=["collaborator", "ml", "genomics"],
            content="Leading researcher in applying machine learning to genomic data analysis. Currently working on deep learning models for variant calling and has published extensively on neural networks for biological sequence analysis.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id=person_ids["prof_johnson"],
            type="person",
            properties={
                "name": "Prof. Michael Johnson",
                "role": "Department Head",
                "department": "Applied Mathematics",
                "email": "m.johnson@university.edu",
                "expertise": [
                    "differential equations",
                    "numerical methods",
                    "climate modeling",
                ],
            },
            tags=["supervisor", "mathematics", "climate"],
            content="Veteran applied mathematician with 20+ years experience in numerical methods for climate science. Expert in solving large-scale differential equation systems and currently supervising multiple PhD students in computational climate research.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id=person_ids["alex_kim"],
            type="person",
            properties={
                "name": "Alex Kim",
                "role": "PhD Student",
                "department": "Computer Science",
                "email": "a.kim@university.edu",
                "advisor": person_ids["prof_johnson"],
                "year": 3,
                "thesis_topic": "Neural ODEs for Climate Prediction",
            },
            tags=["student", "neural-odes", "climate"],
            content="Third-year PhD student specializing in neural ordinary differential equations. Working on incorporating physical constraints into neural network architectures for improved climate modeling accuracy.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id=person_ids["dr_martinez"],
            type="person",
            properties={
                "name": "Dr. Elena Martinez",
                "role": "Postdoc",
                "department": "Environmental Science",
                "email": "e.martinez@university.edu",
                "expertise": ["atmospheric physics", "data analysis", "remote sensing"],
            },
            tags=["postdoc", "climate", "atmospheric-science"],
            content="Postdoctoral researcher with expertise in atmospheric physics and remote sensing. Provides domain expertise for climate modeling projects and manages large-scale atmospheric datasets.",
            created_at=base_time,
            updated_at=base_time,
        ),
        # Projects
        Note(
            id=project_ids["neural_odes"],
            type="project",
            properties={
                "title": "Neural ODEs for Climate Modeling",
                "status": "active",
                "funding": "NSF Grant #2024-001",
                "start_date": "2024-01-15",
                "team_size": 4,
                "supervisor": person_ids["prof_johnson"],
                "lead_developer": person_ids["alex_kim"],
                "collaborators": [person_ids["sarah_chen"]],
                "related_papers": [
                    paper_ids["neural_odes_nature"],
                    paper_ids["climate_review"],
                ],
            },
            tags=["climate", "neural-odes", "differential-equations", "active"],
            content="Investigating the use of Neural Ordinary Differential Equations for modeling complex climate systems. The project aims to improve long-term climate predictions by incorporating physical constraints into neural network architectures.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id=project_ids["genomics_pipeline"],
            type="project",
            properties={
                "title": "Genomic Variant Detection Pipeline",
                "status": "completed",
                "funding": "NIH Grant #2023-BIO-998",
                "start_date": "2023-03-01",
                "end_date": "2024-05-30",
                "team_size": 6,
                "lead": person_ids["sarah_chen"],
                "equipment_used": [equipment_ids["gpu_cluster"]],
            },
            tags=["genomics", "bioinformatics", "completed", "pipeline"],
            content="Successfully developed and deployed a machine learning pipeline for detecting genomic variants from sequencing data. The system processes over 1000 genomes per day and has been adopted by three major research hospitals.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id=project_ids["graph_networks"],
            type="project",
            properties={
                "title": "Physics-Informed Graph Networks",
                "status": "planning",
                "anticipated_start": "2025-09-01",
                "duration": "2 years",
                "team_size": 3,
                "supervisor": person_ids["prof_johnson"],
                "related_projects": [project_ids["neural_odes"]],
            },
            tags=["graph-networks", "physics-informed", "planning"],
            content="Proposed project to develop graph neural networks that incorporate physical laws for modeling complex systems. Will build on insights from the Neural ODEs project to handle irregular spatial data.",
            created_at=base_time,
            updated_at=base_time,
        ),
        # Papers
        Note(
            id=paper_ids["neural_odes_nature"],
            type="paper",
            properties={
                "title": "Physics-Constrained Neural ODEs for Climate Prediction",
                "authors": [
                    person_ids["alex_kim"],
                    person_ids["prof_johnson"],
                    person_ids["dr_martinez"],
                ],
                "journal": "Nature Climate Change",
                "status": "published",
                "publication_date": "2024-08-15",
                "doi": "10.1038/s41558-024-02089-x",
                "related_project": project_ids["neural_odes"],
            },
            tags=["publication", "nature", "neural-odes", "climate"],
            content="Breakthrough paper demonstrating how neural ordinary differential equations can be constrained by physical laws to improve climate prediction accuracy by 23% over traditional methods.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id=paper_ids["genomics_mlsys"],
            type="paper",
            properties={
                "title": "Scalable Deep Learning for Genomic Variant Calling",
                "authors": [person_ids["sarah_chen"]],
                "conference": "MLSys 2024",
                "status": "accepted",
                "publication_date": "2024-03-20",
                "related_project": project_ids["genomics_pipeline"],
            },
            tags=["publication", "mlsys", "genomics", "deep-learning"],
            content="Presents the architecture and performance results of our genomic variant detection pipeline, showing 15x speedup over existing methods while maintaining 99.7% accuracy.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id=paper_ids["climate_review"],
            type="paper",
            properties={
                "title": "Machine Learning in Climate Science: A Comprehensive Review",
                "authors": [person_ids["prof_johnson"], person_ids["dr_martinez"]],
                "journal": "Reviews of Geophysics",
                "status": "under_review",
                "submitted_date": "2024-11-01",
            },
            tags=["review", "climate", "machine-learning", "under-review"],
            content="Comprehensive review of machine learning applications in climate science over the past decade, identifying key challenges and future research directions.",
            created_at=base_time,
            updated_at=base_time,
        ),
        # Grant
        Note(
            id=grant_ids["nsf_climate"],
            type="grant",
            properties={
                "title": "NSF Climate AI Initiative",
                "amount": 2500000,
                "duration": "3 years",
                "status": "submitted",
                "PI": person_ids["prof_johnson"],
                "co_PI": person_ids["sarah_chen"],
                "funded_projects": [
                    project_ids["neural_odes"],
                    project_ids["graph_networks"],
                ],
                "equipment": equipment_ids["gpu_cluster"],
            },
            tags=["funding", "nsf", "climate", "ai", "submitted"],
            content="Major grant proposal to develop AI methods for climate prediction and adaptation. Will fund expansion of Neural ODEs project and development of Physics-Informed Graph Networks. Equipment budget includes upgrading GPU cluster.",
            created_at=base_time,
            updated_at=base_time,
        ),
        # Equipment
        Note(
            id=equipment_ids["gpu_cluster"],
            type="equipment",
            properties={
                "name": "High-Performance GPU Cluster",
                "model": "NVIDIA DGX A100",
                "nodes": 8,
                "total_gpus": 64,
                "memory_per_node": "1TB",
                "location": "Data Center Room 205",
                "purchase_date": "2023-06-15",
                "cost": 800000,
                "projects_using": [
                    project_ids["neural_odes"],
                    project_ids["genomics_pipeline"],
                ],
            },
            tags=["gpu", "cluster", "shared-resource", "nvidia"],
            content="Primary computational resource for deep learning research. Shared across multiple projects requiring high-performance computing. Managed by IT department with job scheduling system.",
            created_at=base_time,
            updated_at=base_time,
        ),
        # Ideas and Meetings
        Note(
            id="e8f9a0b1-c2d3-4e5f-6789-0123456789ab",
            type="idea",
            properties={
                "concept": "Quantum-Informed Neural Networks",
                "maturity": "brainstorming",
                "potential_applications": ["quantum chemistry", "materials science"],
                "inspiration_source": "Discussion with quantum computing group",
            },
            tags=["quantum", "neural-networks", "early-stage"],
            content="Explore incorporating quantum mechanical principles into neural network architectures. Could potentially solve quantum many-body problems more efficiently than classical methods.",
            created_at=base_time,
            updated_at=base_time,
        ),
        Note(
            id="24c744d6-04b0-46a9-9ee3-873c110f7df9",
            type="meeting",
            properties={
                "date": "2024-06-15",
                "attendees": [
                    person_ids["sarah_chen"],
                    person_ids["prof_johnson"],
                    person_ids["alex_kim"],
                ],
                "duration": "2 hours",
                "location": "Conference Room B",
                "discussed_project": project_ids["neural_odes"],
                "shared_resource": equipment_ids["gpu_cluster"],
            },
            tags=["collaboration", "planning", "neural-odes"],
            content="Discussed potential collaboration on neural ODEs project. Dr. Chen offered access to her genomics expertise for cross-domain validation of ODE techniques. Agreed to share computational resources and co-author a paper on applications across biology and climate science.",
            created_at=base_time,
            updated_at=base_time,
        ),
    ]

    return notes


def get_fixture_scopes():
    """Define which notes should be in global vs local scope for testing."""
    return {
        "global": [
            "cbd05128-c5f2-4642-9e11-54b46eef4c8e",  # Dr. Sarah Chen
            "320bd1c6-850f-4bbf-917e-ff7050723172",  # Prof. Johnson
            "da2f1400-fc96-42eb-abea-3ffe81bcafbc",  # NSF Grant
            "fd41f4e6-0189-4bdc-8821-697bba780a02",  # GPU Cluster
            "ac82e618-d60b-44d5-a7ea-04bb5a8092b1",  # Nature paper
        ],
        "local": [
            "792b6ce9-0260-4c53-a008-884b691ea015",  # Alex Kim
            "b8e4d2c1-3f7a-4b9e-8c6d-1a2b3c4d5e6f",  # Dr. Martinez
            "9ea1e787-78f2-45e8-8b33-8df0e130beb8",  # Neural ODEs project
            "4acbb6e9-f777-4699-94de-3ea39f1e146a",  # Genomics pipeline
            "2a74494f-ab7f-41d4-9c91-2bf4430c2e3b",  # Graph networks
            "00f30024-391e-451f-9f48-092702ed8595",  # MLSys paper
            "fe123456-789a-bcde-f012-3456789abcde",  # Climate review
            "e8f9a0b1-c2d3-4e5f-6789-0123456789ab",  # Quantum idea
            "24c744d6-04b0-46a9-9ee3-873c110f7df9",  # Meeting
        ],
    }
