# Límites de persistencia

Import Cars usa tres bases SQLite físicamente separadas. Compartir proceso o
panel de lectura no autoriza a mezclar sus tablas ni sus responsabilidades.

| Base | Variable de entorno | Responsabilidad |
| --- | --- | --- |
| Fiscal | `IMPORT_CARS_FISCAL_DATABASE_PATH` | Fuentes oficiales del BOE y tablas de valoración. |
| Actividad | `IMPORT_CARS_CUSTOMER_DATABASE_PATH` | Cálculos de clientes, auditorías congeladas, eventos y leads. |
| Mercado | `IMPORT_CARS_MARKET_DATABASE_PATH` | Barridos, anuncios, observaciones y precios históricos. |

`IMPORT_CARS_DATABASE_PATH` se conserva temporalmente como alias de la base
fiscal para instalaciones anteriores. Nunca se usa como destino implícito de
leads o de seguimiento de mercado.

Las migraciones se registran por componente en `schema_migrations`. El panel
admin compondrá consultas de repositorios independientes; no habrá claves
foráneas entre bases ni escrituras cruzadas.

## Contratos que no deben romperse

- La API pública solo devuelve precio final, referencia española, ahorro,
  desglose breve, avisos y trazabilidad fiscal pública.
- Los detalles de auditoría y comparables crudos solo existirán tras
  autenticación administrativa.
- El motor fiscal sigue siendo la única fuente de fórmulas e intermedios.
- La política actual de emparejamiento queda caracterizada antes de hacerla
  observable y no se endurece en esta fase.
