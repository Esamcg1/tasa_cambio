# -*- coding: utf-8 -*-
{
    'name': "tasa_cambio",
    'summary': """Obtener tasa cambio del banco de Guatemala""",
    'description': """Obtener tasa cambio del banco de Guatemala""",
    'author': "Erik Yol",
    'website': "mcsistemas.net",
    'category': 'account',
    'version': '0.1',
    'depends': ['base','mail'],
    'data': [
        # 'security/ir.model.access.csv',
        'data/cron_tasa_cambio.xml',
        'views/res_currency.xml',
    ],
    'installable': True,    
    'auto_install': True,
    'application': False
}