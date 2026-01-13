"""XNAT services module.

This module provides a modular, service-oriented architecture for XNAT operations.
Each service handles a specific domain of functionality.

Services:
    XNATConnection: Core connection and HTTP management
    ProjectService: Project, subject, session management
    ScanService: Scan operations (CRUD, listing)
    UploadService: File uploads (resources, DICOM archives)
    DownloadService: File downloads and extraction
    AdminService: Administrative operations (catalogs, users, renaming)

Usage:
    from xnatio.services import XNATConnection, ProjectService, ScanService

    conn = XNATConnection.from_config(cfg)
    projects = ProjectService(conn)
    scans = ScanService(conn)

    projects.create_project("MYPROJECT")
    scans.list_scans("MYPROJECT", "SUBJ001", "SESS001")

For backward compatibility, XNATClient is available as a facade
that combines all services.
"""

from .admin import AdminService
from .base import XNATConnection
from .downloads import DownloadService
from .projects import ProjectService
from .scans import ScanService
from .uploads import UploadService

__all__ = [
    "XNATConnection",
    "ProjectService",
    "ScanService",
    "UploadService",
    "DownloadService",
    "AdminService",
]
