# | Fecha      | Nombre   | Que se hizo |
# |------------|----------|-------------|
# | 2026-11-06 | Arekkazu | M07 RF-97 CA-14: réplica del esquema que valida AgroFusion |
"""Réplica de ``AccountingConsultResponse`` de AgroFusion (``agrofusion-backendint``,
``app/schemas/checks.py``), con los mismos nombres y tipos. Si el envelope no valida aquí,
AgroFusion responde 502 al usuario. Mantener sincronizada con su código."""
from typing import Any, List, Optional

from pydantic import BaseModel


class RequestedPeriod(BaseModel):
    From: str
    To: str


class SourceSystem(BaseModel):
    SystemId: str
    SystemName: str
    SystemNIT: str
    Environment: str


class Metadata(BaseModel):
    ExchangeId: str
    GeneratedAt: str
    StandardVersion: str
    RequestedPeriod: RequestedPeriod
    SourceSystem: SourceSystem
    GeneratedBy: str


class Summary(BaseModel):
    TotalDocuments: int
    TotalInvoices: int
    TotalTransactions: int
    TotalGrossAmount: float
    TotalNet: float
    Currency: str


class DocumentType(BaseModel):
    Code: str
    Name: str


class InvoiceHeader(BaseModel):
    DocumentId: str
    Prefix: str
    Serial: str
    Type: DocumentType
    IssueDate: str
    DueDate: str
    Status: str
    UpdatedAt: str


class ThirdParty(BaseModel):
    NIT: Optional[str]
    Name: str
    Address: Optional[str] = None
    City: Optional[str] = None
    Country: Optional[str] = None
    Email: Optional[str] = None


class InvoiceTotals(BaseModel):
    Subtotal: float
    TotalVAT: float
    TotalWithholdings: float
    TotalDiscounts: float
    TotalPayment: float
    OutstandingBalance: float


class InvoiceLine(BaseModel):
    Code: str
    Name: str
    Description: str
    LineType: str
    accounting_account: List[str]
    Quantity: float
    UnitPrice: float
    Value: float
    Taxes: List[Any] = []


class Invoice(BaseModel):
    Header: InvoiceHeader
    ThirdParty: ThirdParty
    Totals: InvoiceTotals
    Lines: List[InvoiceLine]


class AccountingConsultResponse(BaseModel):
    metadata: Metadata
    summary: Summary
    invoices: List[Invoice]
    transactions: List[Any]
