# PlantUML architecture diagrams

These diagrams describe the implemented Asset Report Generator at two matching levels. Package diagrams show the real Python packages, modules, and imports. Class diagrams expand those modules into their current constructors, public methods, important private helpers, protocols, dataclasses, compositions, and collaborations.

## Diagram set

| ID | Scope | Package diagram | Class diagram |
| --- | --- | --- | --- |
| 00 | Complete system | `package_diagrams/00_system_package_diagram.puml` | `00_system_class_diagram.puml` |
| 01 | Presentation layer | `package_diagrams/01_presentation_layer_packages.puml` | `01_presentation_layer_classes.puml` |
| 02 | Application layer | `package_diagrams/02_application_layer_packages.puml` | `02_application_layer_classes.puml` |
| 03 | Business logic layer | `package_diagrams/03_business_logic_layer_packages.puml` | `03_business_logic_layer_classes.puml` |
| 04 | Domain layer | `package_diagrams/04_domain_layer_packages.puml` | `04_domain_layer_classes.puml` |
| 05 | Data-access layer | `package_diagrams/05_data_access_layer_packages.puml` | `05_data_access_layer_classes.puml` |
| 06 | Output layer | `package_diagrams/06_output_layer_packages.puml` | `06_output_layer_classes.puml` |

The presentation layer is implemented with module-level functions, so its diagram uses a `<<module>>` classifier instead of inventing a Python class that does not exist.

## Consistency rules

- Both sets use IDs `00` through `06`, identical layer names, and identical layer colors.
- Package dependencies are based on imports in the Python source. The repository adapter's structural conformance to the domain protocol is additionally identified as a design-time contract.
- Every class in a layer diagram belongs to a module shown in its paired package diagram.
- Cross-layer arrows use the same direction in both views: presentation → application; application → business/domain/data access/output; business and data access → domain; output → business.
- The domain layer is the stable core and has no dependency on another project layer.

## Rendering

With the PlantUML command-line tool installed, run this from the project root:

```sh
plantuml docs/plantuml/*.puml docs/plantuml/package_diagrams/*.puml
```

To generate SVG instead of PNG:

```sh
plantuml -tsvg docs/plantuml/*.puml docs/plantuml/package_diagrams/*.puml
```

PlantUML editor extensions can also preview each `.puml` file directly.

## Syntax validation

Check every source file without generating images:

```sh
java -jar plantuml.jar -checkonly -failfast2 \
  docs/plantuml/*.puml \
  docs/plantuml/package_diagrams/*.puml
```

The distributed diagram set has been checked successfully with the official PlantUML 1.2026.9 parser.

## Copying source safely

Use the raw `.puml` files rather than copying syntax from an HTML-rendered preview. Text such as `&#x20;`, `&lt;`, `&gt;`, escaped `\<` characters, or a trailing prose period is HTML/Markdown encoding and is not valid PlantUML source. For example, the application package declaration must remain:

```plantuml
package "Application Layer" #E3EEFF {
  class ApplicationConfig <<dataclass>>
}
```
