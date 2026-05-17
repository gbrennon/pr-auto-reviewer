---
id: scala-pattern-matching
language: scala
priority: 85
category: correctness
---

# Scala Pattern Matching Review

Review the following Scala code for proper pattern matching:

```scala
{{ code }}
```

## Checks

- Non-exhaustive `match` expressions on sealed traits/classes (compiler warning ignored)
- Using `case _ =>` wildcard that silently swallows unhandled cases
- Pattern matching where polymorphism or type-classes would be cleaner
- Matching on `Option`/`Either`/`Try` with verbose patterns instead of `.map()`/`.flatMap()`
- Checking types with `.isInstanceOf`/`.asInstanceOf` instead of pattern matching
- `match` on tuples with unnecessary nesting
- Missing `@unchecked` annotation when intentionally suppressing exhaustiveness warnings

## Good Example

```scala
sealed trait PaymentMethod
case class CreditCard(number: String, expiry: String) extends PaymentMethod
case class PayPal(email: String) extends PaymentMethod
case class BankTransfer(iban: String) extends PaymentMethod

def processPayment(method: PaymentMethod): String = method match
  case CreditCard(number, _) =>
    s"Processing credit card ending in ${number.takeRight(4)}"
  case PayPal(email) =>
    s"Processing PayPal from $email"
  case BankTransfer(iban) =>
    s"Processing bank transfer to $iban"
// Compiler ensures exhaustiveness — no wildcard needed
```

## Bad Example

```scala
def processPayment(method: Any): String = method match
  case m: CreditCard => s"CC: ${m.number}"
  case m: PayPal     => s"PP: ${m.email}"
  case _             => "Unknown"  // Wildcard hides missing BankTransfer case
  // No sealed trait — new payment methods silently fall to wildcard
```
