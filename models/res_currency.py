from odoo import models, fields, api
from odoo.exceptions import ValidationError
from datetime import datetime
import requests
import xmltodict
import logging

# logger = logging.getLogger(name_)

class ResCurrencyRate(models.Model):
    _inherit = 'res.currency.rate'
    _description = 'Campo tasa de cambio Banguat'
    
    tasa_banguat = fields.Float(string='Tasa Banguat', digits=(12, 5), default=1.0, 
                               help='tasa de cambio del Banco de Guatemala')

    def _get_currency_mapping(self):
        """Define el mapeo entre códigos Odoo y Banguat"""
        return {
            'USD': 1,  # dolar americado
            'GTQ': 2,  # Quetzal
            'EUR': 3,  # Euro
            'MXN': 4,  # Peso Mexicano
        }

    def _call_banguat_api(self, xml_body):
        """metodo para llamar a la api del BANGUAT"""
        url_ws = 'https://www.banguat.gob.gt/variables/ws/TipoCambio.asmx?wsdl'
        headers = {'Content-Type': 'text/xml'}
        
        try:
            response = requests.post(url_ws, data=xml_body, headers=headers, timeout=30)
            response.raise_for_status()
            xml_text = response.text
            return xmltodict.parse(xml_text)
        except requests.exceptions.RequestException as e:
            _logger.error("Error conectando a Banguat: %s", str(e))
            raise ValidationError(_('Error de conexión con Banguat: {}').format(str(e)))
        except Exception as e:
            _logger.error("Error procesando respuesta de Banguat: %s", str(e))
            raise ValidationError(_('Error procesando respuesta de Banguat: {}').format(str(e)))

    def get_currency_rate_by_code(self, banguat_code):
        """obtener la tasa de cambio para un codigo del BANGUAT"""
        xml = """
        <soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" 
                          xmlns:ws="http://www.banguat.gob.gt/variables/ws/">
            <soapenv:Header/>
            <soapenv:Body>
                <ws:Variables>
                    <ws:variable>{banguat_code}</ws:variable>
                </ws:Variables>
            </soapenv:Body>
        </soapenv:Envelope>
        """
        
        try:
            response_dict = self._call_banguat_api(xml)
            
            # Procesar la respuesta para tasas de monedas extranjeras
            vars_data = response_dict.get('soap:Envelope', {}).get('soap:Body', {}).get('VariablesResponse', {}).get('VariablesResult', {})
            
            if vars_data.get('CambioDia'):
                var_data = vars_data['CambioDia']['Var']
                if isinstance(var_data, list):
                    var_data = var_data[0]  # Tomar el primer elemento si es lista
                
                return {
                    'fecha': var_data.get('fecha'),
                    'venta': float(var_data.get('venta', 0)),
                    'compra': float(var_data.get('compra', 0)),
                    'referencia': (float(var_data.get('venta', 0)) + float(var_data.get('compra', 0))) / 2
                }
            
        except Exception as e:
            _logger.error("Error obteniendo tasa para código %s: %s", banguat_code, str(e))
        
        return None

    def get_all_active_currency_rates(self):
        """
        Obtener las monedas activas en Odoo, mapear los códigos de Banguat 
        y consultar las tasas de cambio
        """
        # hacer la busqueda en las monedas activas
        active_currencies = self.env['res.currency'].search([('active', '=', True)])
        currency_mapping = self._get_currency_mapping()
        
        rates = {}
        for currency in active_currencies:
            banguat_code = currency_mapping.get(currency.name)
            if banguat_code:
                rate_data = self.get_currency_rate_by_code(banguat_code)
                if rate_data:
                    rates[currency.name] = rate_data
                    # _logger.info("Tasa obtenida para %s: %s", currency.name, rate_data)
                else:
                    raise ValidationError(_('No se pudo obtener la tasa para la moneda: {}').format(currency.name))
            else:
                raise ValidationError(_('No hay mapeo de Banguat para la moneda: {}').format(currency.name))
        
        return rates

    def create_currency_rates(self, rates_data):
        """Crea registros de tasas de cambio en Odoo"""
        created_rates = []
        
        for currency_name, rate_info in rates_data.items():
            currency = self.env['res.currency'].search([('name', '=', currency_name)], limit=1)
            if not currency:
                raise ValidationError(_('Moneda no encontrada en Odoo: {}').format(currency_name))
                continue
            
            # Convertir fecha
            try:
                fecha = datetime.strptime(rate_info['fecha'], '%d/%m/%Y').date()
            except ValueError:
                raise ValidationError(_('Formato de fecha inválido para la moneda: {}').format(currency_name))
                continue
            
            # Verificar si ya existe el registro
            existing_rate = self.search([
                ('name', '=', fecha),
                ('currency_id', '=', currency.id)
            ])
            
            if existing_rate:
                raise ValidationError(_('La tasa para la moneda {} en la fecha {} ya existe.').format(currency_name, fecha))
                continue
            
            # Usar tasa de referencia (promedio entre compra y venta)
            tasa = rate_info.get('referencia', 1.0)
            
            # Para GTQ, la tasa debe ser 1.0 (moneda base)
            if currency_name == 'GTQ':
                tasa = 1.0
            
            rate_record = self.sudo().create({
                'name': fecha,
                'rate': 1.0 / tasa if currency_name != 'GTQ' else 1.0,  # Invertir para Odoo
                'tasa_banguat': tasa,
                'currency_id': currency.id,
            })
            
            created_rates.append(rate_record)
            # _logger.info("Creada tasa para %s: %s", currency_name, tasa)
        
        return created_rates

    @api.model
    def update_all_currency_rates(self):
        """actualizar todas las tasas con CRON"""
        # _logger.info("Iniciando actualización de tasas de cambio desde Banguat")
        
        try:
            # Obtener todas las tasas
            rates_data = self.get_all_active_currency_rates()
            
            if not rates_data:
                raise ValidationError(_('No se obtuvieron tasas de cambio desde Banguat.'))
                return False
            
            # Crear registros en Odoo
            created_rates = self.create_currency_rates(rates_data)
            
            # _logger.info("Actualización completada. %s tasas creadas/actualizadas", len(created_rates))
            return True
            
        except Exception as e:
            # _logger.error("Error en actualización de tasas: %s", str(e))
            raise ValidationError(_('Error actualizando tasas: {}').format(str(e)))

    # Mantener compatibilidad con el método antiguo
    @api.model
    def get_tipo_cambio_dia(self):
        """Método legacy - ahora usa el nuevo sistema"""
        return self.update_all_currency_rates()