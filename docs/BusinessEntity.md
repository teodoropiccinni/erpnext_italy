# BusinessEntity Architecture for ERPNext

## Objective

Introduce a new master DocType named **BusinessEntity** to centralize the management of business partners that may act as both Customers and Suppliers.

The goal is to eliminate duplicate maintenance while remaining fully compatible with the ERPNext standard.

ERPNext will continue using its native `Customer` and `Supplier` DocTypes. These become synchronized representations of the master `BusinessEntity`.

---

# Architecture

```
               BusinessEntity
                     │
        ┌────────────┴────────────┐
        │                         │
   Customer                  Supplier
        │                         │
        └────────── ERPNext ──────┘
```

`BusinessEntity` is the **Single Source of Truth** for all shared business information.

`Customer` and `Supplier` continue to exist because they are required by the ERPNext core and by all standard transactions.

---

# Design Principles

- BusinessEntity is the master record.
- Customer and Supplier remain standard ERPNext DocTypes.
- Shared information is maintained only once.
- Customer and Supplier are created and synchronized automatically.
- No modifications to ERPNext core.
- Full compatibility with future ERPNext upgrades.

---

# BusinessEntity DocType

## General Information

- Business Name
- Legal Name
- VAT Number
- Tax Code
- Company Type
- Language
- Currency

---

## Roles

- Is Customer
- Is Supplier

These flags determine whether a linked Customer and/or Supplier should exist.

---

## Contacts

- Email
- PEC
- Phone
- Mobile
- Website

---

## Addresses

Use the standard ERPNext `Address` DocType through Dynamic Links.

No duplicated address information should be stored.

---

## ERP References

Hidden fields:

- customer
- supplier

These fields store the linked ERPNext documents.

---

# Synchronization Flow

## Creation

```
BusinessEntity
        │
        ├── Is Customer
        │        │
        │        ▼
        │   Create Customer
        │
        └── Is Supplier
                 │
                 ▼
           Create Supplier
```

Whenever a BusinessEntity is created:

- If **Is Customer** is enabled, create or update the corresponding Customer.
- If **Is Supplier** is enabled, create or update the corresponding Supplier.

---

# Update Flow

```
BusinessEntity
        │
        ├────────► Customer
        │
        └────────► Supplier
```

Any modification made to BusinessEntity is propagated automatically.

Fields synchronized include:

- Name
- VAT Number
- Tax Code
- Currency
- Language
- Payment Terms
- Tax Category
- Territory
- Contact Information

---

# Direct Customer/Supplier Creation

ERPNext users may still create Customers or Suppliers directly.

To preserve compatibility, the following flow should be implemented.

## Customer

```
Customer Created
        │
        ▼
Search BusinessEntity
        │
        ├── Found
        │      │
        │      ▼
        │   Link Customer
        │
        └── Not Found
               │
               ▼
      Create BusinessEntity
```

The lookup priority should be:

1. VAT Number
2. Tax Code
3. Company Name (optional)

---

## Supplier

Exactly the same workflow should be applied.

---

# Conflict Resolution

BusinessEntity remains the authoritative source.

```
BusinessEntity
        │
        ├── Customer
        └── Supplier
```

Rules:

- Changes made on BusinessEntity are propagated immediately.
- Changes made directly on Customer update BusinessEntity.
- Changes made directly on Supplier update BusinessEntity.
- BusinessEntity then propagates the update to the opposite entity.

This guarantees that all three documents remain synchronized.

---

# Dashboard

BusinessEntity should provide a unified dashboard.

## Sales

- Quotations
- Sales Orders
- Delivery Notes
- Sales Invoices

---

## Purchases

- Supplier Quotations
- Purchase Orders
- Purchase Receipts
- Purchase Invoices

---

## Accounting

- Journal Entries
- Payment Entries

This provides a complete overview of the business relationship with a company.

---

# Migration Strategy

Migration should be automatic.

For every existing Customer:

1. Search BusinessEntity by VAT Number.
2. If found:
   - link Customer.
3. Otherwise:
   - create BusinessEntity.

Repeat the same process for Suppliers.

If both Customer and Supplier share the same VAT Number:

```
BusinessEntity
        │
        ├── Customer
        └── Supplier
```

they become linked to the same master record.

---

# Naming

BusinessEntity

```
BE-.YYYY.-.#####
```

Customer

Standard ERPNext naming.

Supplier

Standard ERPNext naming.

---

# Advantages

- No ERPNext core modifications.
- Fully upgrade-safe.
- Eliminates duplicated maintenance.
- Single source of truth.
- Simplifies migration from legacy ERP systems.
- Improves reporting and analytics.
- Reduces synchronization errors.
- Allows unified customer/supplier management.

---

# Future Extensions

BusinessEntity could become the common registry for additional ERPNext entities, including:

- Customer
- Supplier
- Sales Partner
- Prospect
- Dealer
- Service Provider

This would establish BusinessEntity as the central business registry for the entire ERP ecosystem while preserving full compatibility with the ERPNext core.