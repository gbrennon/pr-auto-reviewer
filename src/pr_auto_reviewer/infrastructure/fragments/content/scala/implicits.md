---
id: scala-implicits
language: scala
priority: 70
category: best-practices
---

# Scala Implicits / Given Review

Review the following Scala code for proper implicit/given usage:

```scala
{{ code }}
```

## Checks

- `implicit` conversions (Scala 2) used without `scala.language.implicitConversions` import
- Implicit conversions that could hide bugs by silently converting types
- Multiple implicit values of the same type in scope (ambiguous implicits)
- Using `implicit` parameters where `given`/`using` (Scala 3) would be clearer
- `ExecutionContext` passed implicitly without clear naming
- Implicit `Numeric`/`Ordering` conflicts
- Type class instances defined as `implicit` in random places instead of companion objects

## Good Example

```scala
// Scala 3 — given/using
trait JsonWriter[A]:
  def write(value: A): Json

object JsonWriter:
  given JsonWriter[String] with
    def write(value: String): Json = JsonString(value)

  given [A](using writer: JsonWriter[A]): JsonWriter[List[A]] with
    def write(values: List[A]): Json =
      JsonArray(values.map(writer.write))

def toJson[A](value: A)(using writer: JsonWriter[A]): Json =
  writer.write(value)
```

## Bad Example

```scala
// Scala 2 implicit conversion without explicit opt-in
implicit def stringToInt(s: String): Int = s.toInt
// Silently converts strings to ints — hides errors

def calculate(a: Int, b: Int): Int = a + b

val result = calculate("10", "20")  // Works? Or throws? Unclear at call site.
```
