# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import RedirectWarning, UserError, ValidationError
import requests
import xmltodict
import pytz
import datetime


class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'
    _description = 'Campo tasa de cambio Banguat'
    
    tasa_banguat = fields.Float(string='Tasa Banguat',digits=(12, 5), default=1.0, help='tasa de cambio del Banco de Guatemala')
    
    @api.multi
    def get_tipo_cambio_dia(self):
        
        url_ws = 'https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?wsdl'

        xml = """
                <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:ws="http://www.banguat.gob.gt/variables/ws/">
                <soapenv:Header/>
                <soapenv:Body>
                    <ws:TipoCambioDia/>
                </soapenv:Body>
                </soapenv:Envelope>
            """
        
        headers = {
                'Content-Type': 'text/xml'
            }
        
        try:
            response = requests.post(url_ws, data=xml, headers=headers)
            xml_text = response.text
            responseDict = xmltodict.parse(xml_text)
            
            _fecha = responseDict['soap:Envelope']['soap:Body']['TipoCambioDiaResponse']['TipoCambioDiaResult']['CambioDolar']['VarDolar']['fecha']
            _tasa = responseDict['soap:Envelope']['soap:Body']['TipoCambioDiaResponse']['TipoCambioDiaResult']['CambioDolar']['VarDolar']['referencia']

            fecha = datetime.datetime.strptime(_fecha,'%d/%m/%Y')
            tasa = float(_tasa)
            quetzal = self.env['res.currency'].search([('name','=','GTQ'),('symbol','=','Q')])
            fecha_existe = self.search([('name','=',fecha),('currency_id','=',quetzal.id)])

            if not fecha_existe:
                print('No existe el registro')

                self.sudo().create({
                    'name': fecha,
                    'rate': tasa,
                    'tasa_banguat': tasa,
                    'currency_id': quetzal.id,
                })

        except Exception as ex:
                print("Error",ex)
                raise ValidationError(_('Exception: {}').format(str(ex)))