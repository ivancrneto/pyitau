import os
from datetime import datetime
from pathlib import Path

import requests
from cached_property import cached_property

from pyitau.pages import (AuthenticatedHomePage, BiggerMenuPage, CardDetails,
                          CheckingAccountFullStatement, CheckingAccountMenu,
                          CheckingAccountStatementsPage, FirstRouterPage,
                          MenuPage, PasswordPage, PixPage, SecondRouterPage,
                          ThirdRouterPage)

ROUTER_URL = 'https://internetpf5.itau.com.br/router-app/router'


class Itau:
    def __init__(self, agency, account, account_digit, password, holder_name=None):
        self.agency = agency
        self.account = account
        self.account_digit = account_digit
        self.password = password
        self.holder_name = holder_name
        self._session = requests.Session()
        self._session.headers = {
            **self._session.headers,
            'User-Agent': (
                'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 '
                '(KHTML, like Gecko) Ubuntu Chromium/72.0.3626.121 '
                'Chrome/72.0.3626.121 Safari/537.36'
            ),
        }

    def authenticate(self):
        self._authenticate2()
        self._authenticate3()
        self._authenticate4()
        self._authenticate5()
        self._authenticate6()
        self._authenticate7()
        self._authenticate8()
        self._authenticate9()

    def get_credit_card_invoice(self, card_name=None):
        """
        Get and return the credit card invoice.
        """
        headers = {
            "op": self._bigger_menu_page.checking_cards_home_op,
            "X-FLOW-ID": self._flow_id,
            "X-CLIENT-ID": self._client_id,
            "X-Requested-With": "XMLHttpRequest",
        }
        response = self._session.post(ROUTER_URL, headers=headers)
        card_details = CardDetails(response.text)
        card_full_statement_op = card_details.full_statement_op

        response = self._session.post(
            ROUTER_URL,
            headers={"op": card_details.invoice_op},
            data={"secao": "Cartoes", "item": "Home"},
        )
        response_json = response.json()
        cards = response_json["object"]["data"]

        self._session.post(
            ROUTER_URL,
            headers={"op": card_details.invoice_op},
            data={"secao": "Cartoes:MinhaFatura", "item": ""},
        )

        if not card_name:
            card_id = cards[0]['id']
        else:
            card_id = [card for card in cards if card['nome'] == card_name][0]['id']
        response = self._session.post(
            ROUTER_URL, headers={"op": card_full_statement_op}, data=card_id
        )
        return response.json()

    def get_statements(self, days=90):
        """
        Get and return the statements of the last days.
        """

        response = self._session.post(
            ROUTER_URL,
            data={'periodoConsulta': days},
            headers={'op': self._checking_full_statement_page.filter_statements_by_period_op},
        )
        return response.json()

    def get_statements_from_month(self, month=1, year=2001):
        """
        Get and return the full statements of a specific month.
        """
        if year < 2001:
            raise Exception(f"Invalid year {year}.")

        if month < 1 or month > 12:
            raise Exception(f"Invalid month {month}.")

        response = self._session.post(
            ROUTER_URL,
            data={'mesCompleto': "%02d/%d" % (month, year)},
            headers={'op': self._checking_full_statement_page.filter_statements_by_month_op},
        )
        return response.json()

    def get_pix(self, days=90):
        """Get and return the pix transaction for the last {days}."""

        response = self._session.post(
            ROUTER_URL, headers={"op": self._bigger_menu_page.pix_statements_op})
        self.pix_page = PixPage(response.text)

        data = {
            "periodo": f"{days}",
            "page": "1",
            "filtro": "debito",
            "ordenacao": "desc",
        }

        headers = {
            "Op": self.pix_page.pix_statements_op,
            "X-FLOW-ID": self._flow_id,
            "X-CLIENT-ID": self._client_id,
            "X-Requested-With": "XMLHttpRequest",
            "Accept": "application/json, text/javascript, */*; q=0.01",
            "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
        }

        response = self._session.post(ROUTER_URL, data=data, headers=headers)
        return response.json()['lancamentos']

    def get_pix_receipts(self, pix_transactions):
        """Returns a generator containing the binary files of the given pix transactions."""

        headers = {
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
            "Content-type": "application/x-www-form-urlencoded",
            "Op": self.pix_page.pix_impressao_op,
        }

        path = os.path.abspath(Path(__file__) / ".." / "files" / "pix_pdf.html")
        with open(path, "r") as fname:
            template = fname.read()

        for data in pix_transactions:
            final_html = template[:3800] + template[3800:].format(
                literalLancamento=data["literalLancamento"],
                dataHora=data["dataHora"],
                valor=data["valor"],
                fraseTipoLancamento=data["fraseTipoLancamento"],
                nomeFavorecido=data["nomeFavorecido"],
                bancoFavorecido=data["bancoFavorecido"],
                codigoControleCamara=data["codigoControleCamara"],
            )

            payload = {
                "op": "",
                "htmlContent": final_html,
                "titulo": "Detalhes",
                "nomeArquivo": "detalhe-pix",
                "dataHoraAtualizacao": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            }

            yield self._session.post(
                ROUTER_URL,
                data=payload,
                headers=headers,
            )

    def _authenticate2(self):
        data = {
            'portal': '005',
            'pre-login': 'pre-login',
            'tipoLogon': '7',
            'usuario.agencia': self.agency,
            'usuario.conta': self.account,
            'usuario.dac': self.account_digit,
            'destino': '',
        }
        response = self._session.post(ROUTER_URL, data=data)
        page = FirstRouterPage(response.text)
        self._session.cookies.set('X-AUTH-TOKEN', page.auth_token)
        self._op2 = page.secapdk
        self._op3 = page.secbcatch
        self._op4 = page.perform_request
        self._flow_id = page.flow_id
        self._client_id = page.client_id

    def _authenticate3(self):
        headers = {
            'op': self._op2,
            'X-FLOW-ID': self._flow_id,
            'X-CLIENT-ID': self._client_id,
            'renderType': 'parcialPage',
            'X-Requested-With': 'XMLHttpRequest',
        }

        self._session.post(ROUTER_URL, headers=headers)

    def _authenticate4(self):
        headers = {'op': self._op3}
        self._session.post(ROUTER_URL, headers=headers)

    def _authenticate5(self):
        headers = {'op': self._op4}
        response = self._session.post(ROUTER_URL, headers=headers)
        page = SecondRouterPage(response.text)
        self._op5 = page.op_sign_command
        self._op6 = page.op_maquina_pirata
        self._op7 = page.guardiao_cb

    def _authenticate6(self):
        headers = {'op': self._op5}
        self._session.post(ROUTER_URL, headers=headers)

    def _authenticate7(self):
        headers = {'op': self._op6}
        self._session.post(ROUTER_URL, headers=headers)

    def _authenticate8(self):
        headers = {'op': self._op7}
        response = self._session.post(ROUTER_URL, headers=headers)

        page = ThirdRouterPage(response.text)
        if self.holder_name and page.has_account_holders_form:
            holders_op = page.op
            holder, holder_index = page.find_account_holders(self.holder_name)
            headers = {
                "op": holders_op,
            }
            data = {
                "nomeTitular": holder,
                "indexTitular": holder_index,
            }
            self._session.post(ROUTER_URL, headers=headers, data=data)
            self._authenticate6()
            self._authenticate7()
            headers = {"op": self._op7}
            response = self._session.post(ROUTER_URL, headers=headers)

        page = PasswordPage(response.text)
        self._letter_password = page.letter_password(self.password)
        self._op8 = page.op

    def _authenticate9(self):
        headers = {'op': self._op8}
        data = {
            'op': self._op8,
            'senha': self._letter_password
        }

        response = self._session.post(ROUTER_URL, headers=headers, data=data)
        self._home = AuthenticatedHomePage(response.text)

    @cached_property
    def _menu_page(self):
        headers = {'op': self._home.op, 'segmento': 'VAREJO'}
        response = self._session.post(ROUTER_URL, headers=headers)
        return MenuPage(response.text)

    @cached_property
    def _bigger_menu_page(self):
        headers = {'op': self._home.op, 'segmento': 'VAREJO'}
        self._session.post(ROUTER_URL, headers=headers)

        response = self._session.post(ROUTER_URL, headers={"op": self._home.menu_op})
        return BiggerMenuPage(response.text)

    @cached_property
    def _checking_menu_page(self):
        response = self._session.post(
            ROUTER_URL,
            headers={'op': self._menu_page.checking_account_op}
        )
        return CheckingAccountMenu(response.text)

    @cached_property
    def _checking_statements_page(self):
        response = self._session.post(
            ROUTER_URL,
            headers={'op': self._checking_menu_page.statements_op}
        )
        return CheckingAccountStatementsPage(response.text)

    @cached_property
    def _checking_full_statement_page(self):
        response = self._session.post(
            ROUTER_URL,
            headers={'op': self._checking_statements_page.full_statement_op},
        )
        return CheckingAccountFullStatement(response.text)
