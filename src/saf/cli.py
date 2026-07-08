from __future__ import annotations

import argparse

from saf.audit import AuditConfig, run_audit
from saf.database import (
    carregar_banco_demo,
    caminho_banco_padrao,
    caminho_fixtures_padrao,
    gerar_banco_demo_a_partir_de_fixtures,
)
from saf.exporter import exportar_relatorio_contestacao


def main() -> None:
    parser = argparse.ArgumentParser(description="SAF - Sistema de Auditoria de Fretes e Faturas")
    subparsers = parser.add_subparsers(dest="comando", required=True)

    seed_parser = subparsers.add_parser("seed", help="Monta o banco SQLite a partir da massa fornecida.")
    seed_parser.add_argument("--banco", default=str(caminho_banco_padrao()))
    seed_parser.add_argument("--pasta-fixtures", default=str(caminho_fixtures_padrao()))

    audit_parser = subparsers.add_parser("audit", help="Executa a auditoria e gera o relatorio Excel.")
    audit_parser.add_argument("--banco", default=str(caminho_banco_padrao()))
    audit_parser.add_argument("--saida", default="exports/contestacao_frete.xlsx")
    audit_parser.add_argument("--pasta-fixtures", default=str(caminho_fixtures_padrao()))

    api_parser = subparsers.add_parser("api", help="Sobe a API FastAPI do SAF.")
    api_parser.add_argument("--host", default="127.0.0.1")
    api_parser.add_argument("--port", type=int, default=8000)

    args = parser.parse_args()

    if args.comando == "seed":
        caminho = gerar_banco_demo_a_partir_de_fixtures(args.banco, args.pasta_fixtures)
        print(f"Banco de testes gerado a partir dos arquivos fornecidos em: {caminho}")
        return

    if args.comando == "audit":
        gerar_banco_demo_a_partir_de_fixtures(args.banco, args.pasta_fixtures)
        dados = carregar_banco_demo(args.banco)
        audit_df, resumo_df = run_audit(
            dados["erp"],
            dados["fatura"],
            dados["contrato"],
            AuditConfig(),
        )
        saida = exportar_relatorio_contestacao(audit_df, resumo_df, args.saida)
        print(resumo_df.to_string(index=False))
        print(f"Relatorio gerado em: {saida}")
        return

    if args.comando == "api":
        import uvicorn

        uvicorn.run("saf.api:app", host=args.host, port=args.port, reload=False)
        return


if __name__ == "__main__":
    main()
