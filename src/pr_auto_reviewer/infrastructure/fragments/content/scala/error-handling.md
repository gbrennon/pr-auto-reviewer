---
id: scala-error-handling
language: scala
priority: 80
category: error-handling
---

# Scala Error Handling Review

Review the following Scala code for proper error handling:

```scala
{{ code }}
```

## Checks

- Using `try-catch` where `Try`, `Either`, or `Option` would be more idiomatic
- Calling `.get` on `Option` or `Try` without checking — may throw
- `Try(...).get` or `Try(...).getOrElse(throw ...)` chaining
- Throwing exceptions in functional pipelines (.map, .flatMap) instead of using `Either`
- Using `Either` without a meaningful left type (`Either[String, A]` instead of sealed error ADT)
- For-comprehensions on `Either`/`Option`/`Try` that could fail silently
- Mixing `Future` with exceptions without recovery

## Good Example

```scala
sealed trait ConfigError
case class FileNotFound(path: String) extends ConfigError
case class ParseError(cause: Throwable) extends ConfigError

def loadConfig(path: String): Either[ConfigError, Config] =
  for
    content <- readFile(path).left.map(e => FileNotFound(path))
    config  <- parseConfig(content).left.map(ParseError(_))
  yield config

def readFile(path: String): Either[Throwable, String] =
  Try(scala.io.Source.fromFile(path).mkString).toEither
```

## Bad Example

```scala
def loadConfig(path: String): Config = {
  try {
    val content = scala.io.Source.fromFile(path).mkString
    parseConfig(content) match {
      case Right(c) => c
      case Left(e) => throw new RuntimeException(e)  // Throwing from Either
    }
  } catch {
    case e: Exception =>
      println(s"Error: $e")  // Silently swallowing
      null  // Returning null — forces callers to null-check
  }
}
```
