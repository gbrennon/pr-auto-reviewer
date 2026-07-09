---
id: java-immutability
language: java
priority: 75
category: best-practices
---

# Java Immutability Review

Review the following Java code for mutability issues:

```java
{{ code }}
```

## Checks

- Public setters on objects that should be immutable (value objects, DTOs)
- Mutable collections exposed via getters without defensive copies
- Missing `final` on fields that should never change
- Using `Date` or `Calendar` (mutable) instead of `java.time` classes
- Modifying collection parameters passed to a method
- Classes that could be `record` types (Java 14+) but are handwritten
- `static` mutable shared state

## Good Example

```java
public record User(
    long id,
    String name,
    List<String> roles
) {
    public User {
        roles = List.copyOf(roles);  // Defensive copy in compact constructor
    }
}

public final class Money {
    private final BigDecimal amount;
    private final Currency currency;

    public Money(BigDecimal amount, Currency currency) {
        this.amount = amount.setScale(2, RoundingMode.HALF_UP);
        this.currency = Objects.requireNonNull(currency);
    }

    public Money add(Money other) {
        if (!this.currency.equals(other.currency)) {
            throw new IllegalArgumentException("Currency mismatch");
        }
        return new Money(this.amount.add(other.amount), this.currency);
    }
}
```

## Bad Example

```java
public class User {
    private long id;
    private String name;
    private List<String> roles;  // Mutable, public setter modifies internal state

    public List<String> getRoles() {
        return roles;  // Exposes internal mutable list directly
    }

    public void setName(String name) {
        this.name = name;  // Allows arbitrary mutation after construction
    }
}
```
