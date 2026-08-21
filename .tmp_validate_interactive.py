"""Driver PTY para validar o menu interativo no container."""

from __future__ import annotations

import os
import pty
import select
import sys
import time


def drain(fd: int, collected: bytearray, seconds: float) -> str:
    deadline = time.time() + seconds
    while time.time() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.25)
        if not ready:
            continue
        try:
            chunk = os.read(fd, 8192)
        except OSError:
            break
        if not chunk:
            break
        collected.extend(chunk)
        sys.stdout.write(chunk.decode("utf-8", "replace"))
        sys.stdout.flush()
    return collected.decode("utf-8", "replace")


def wait_for(fd: int, collected: bytearray, needle: str, seconds: float) -> None:
    deadline = time.time() + seconds
    while time.time() < deadline:
        text = drain(fd, collected, min(1.0, deadline - time.time()))
        if needle in text:
            return
    tail = collected.decode("utf-8", "replace")[-4000:]
    raise SystemExit(f"timeout waiting for {needle!r}\n--- output ---\n{tail}")


def send(fd: int, data: str) -> None:
    os.write(fd, data.encode("utf-8"))


def run(sequence: list[tuple[str, str, float]], closing: str | None = None) -> str:
    collected = bytearray()
    pid, fd = pty.fork()
    if pid == 0:
        os.execvp("consultor-juridico", ["consultor-juridico"])
    try:
        for needle, payload, timeout in sequence:
            wait_for(fd, collected, needle, timeout)
            if payload == "CTRL_C":
                send(fd, "\x03")
            else:
                send(fd, payload)
        drain(fd, collected, 3)
        if closing:
            wait_for(fd, collected, closing, 10)
        drain(fd, collected, 1)
    finally:
        try:
            os.close(fd)
        except OSError:
            pass
        _, status = os.waitpid(pid, 0)
        if status != 0 and closing:
            raise SystemExit(f"process exited with status {status}")
    return collected.decode("utf-8", "replace")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "menu"

    if mode == "ctrlc":
        output = run(
            [("Menu Principal", "CTRL_C", 60)],
            closing="Saindo... Obrigado por usar o Consultor Jurídico!",
        )
        assert "Menu Principal" in output
        print("\nOK ctrlc")
        return

    if mode == "search":
        output = run(
            [
                ("Menu Principal", "2\n", 60),
                ("Termo ou assunto para pesquisa", "manifestação do pensamento\n", 30),
                ("Principais dispositivos encontrados", "\n", 90),
                ("Menu Principal", "0\n", 30),
            ],
            closing="Saindo... Obrigado por usar o Consultor Jurídico!",
        )
        assert "Explorar / Pesquisar a Constituição" in output
        print("\nOK search")
        return

    if mode == "consult":
        output = run(
            [
                ("Menu Principal", "1\n", 60),
                (
                    "Sua pergunta",
                    "O que a Constituição diz sobre a manifestação do pensamento?\n",
                    30,
                ),
                ("Pressione", "\n", 180),
                ("Menu Principal", "0\n", 30),
            ],
            closing="Saindo... Obrigado por usar o Consultor Jurídico!",
        )
        if (
            "Resposta Fundamentada" not in output
            and "Evidência Insuficiente" not in output
            and "Falha Técnica" not in output
        ):
            raise SystemExit(
                "consulta não produziu painel de resposta, abstenção ou falha técnica"
            )
        print("\nOK consult")
        return

    output = run(
        [
            ("Menu Principal", "3\n", 60),
            ("Estado da Base Jurídica", "\n", 30),
            ("Menu Principal", "4\n", 30),
            ("Diagnóstico Técnico do Sistema", "\n", 30),
            ("Menu Principal", "5\n", 30),
            ("Sobre o Projeto", "\n", 30),
            ("Menu Principal", "0\n", 30),
        ],
        closing="Saindo... Obrigado por usar o Consultor Jurídico!",
    )
    assert "CONSULTOR JURÍDICO" in output
    assert (
        "Processada e materializada" in output or "Aguardando materialização" in output
    )
    assert "PostgreSQL (pgvector)" in output
    print("\nOK menu/status/diagnostics/about/exit")


if __name__ == "__main__":
    main()
