---
id: solid-principles
language: null
priority: 100
category: architecture
---

# SOLID Principles Review

Check for violations of SOLID principles:

```
{{ code }}
```

## Single Responsibility Principle
- Each class/module should have one reason to change
- Look for "god classes" with multiple unrelated responsibilities

## Open/Closed Principle
- Open for extension, closed for modification
- Avoid long if/switch chains for type checking

## Liskov Substitution Principle
- Subtypes must be substitutable for base types
- Check for method signature violations in overrides

## Interface Segregation Principle
- Clients shouldn't depend on interfaces they don't use
- Look for fat interfaces

## Dependency Inversion Principle
- Depend on abstractions, not concretions
- Check for `new ConcreteClass()` instantiations
