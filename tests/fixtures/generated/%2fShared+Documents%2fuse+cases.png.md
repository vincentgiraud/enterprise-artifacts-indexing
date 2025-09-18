
# Description:
Extracted content:

**Roles:**
- Shopper
- Interior Designer
- Store Associate
- Inventory Manager
- Loyalty Programme Manager

**Use Cases:**
- Personalised Product Recommendation
- Customer Query Handling
- In-Store Layout Guidance
- Real-Time Inventory Check
- Offer Triggering at Checkout
- Loyalty Programme Management

**Agents:**
- Shopper Agent
- Interior Design Agent
- Inventory Agent
- Customer Loyalty Agent

---

**Mermaid Code Block:**

```mermaid
graph TD
    subgraph Roles
        Shopper
        InteriorDesigner[Interior Designer]
        StoreAssociate[Store Associate]
        InventoryManager[Inventory Manager]
        LoyaltyProgMgr[Loyalty Programme Manager]
    end

    subgraph UseCases
        ProductRecommendation[Personalised Product Recommendation]
        QueryHandling[Customer Query Handling]
        LayoutGuidance[In-Store Layout Guidance]
        InventoryCheck[Real-Time Inventory Check]
        OfferTrigger[Offer Triggering at Checkout]
        LoyaltyManagement[Loyalty Programme Management]
    end

    subgraph Agents
        ShopperAgent
        DesignAgent[Interior Design Agent]
        InventoryAgent
        LoyaltyAgent[Customer Loyalty Agent]
    end

    Shopper --> ProductRecommendation
    Shopper --> QueryHandling
    Shopper --> LayoutGuidance

    InteriorDesigner --> LayoutGuidance

    StoreAssociate --> InventoryCheck
    StoreAssociate --> QueryHandling

    InventoryManager --> InventoryCheck
    InventoryManager --> OfferTrigger

    LoyaltyProgMgr --> LoyaltyManagement

    ProductRecommendation --> ShopperAgent
    QueryHandling --> ShopperAgent

    LayoutGuidance --> DesignAgent
    InventoryCheck --> InventoryAgent

    OfferTrigger --> InventoryAgent
    LoyaltyManagement --> LoyaltyAgent
```
