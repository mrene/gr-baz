#
# Copyright 2007 Free Software Foundation, Inc.
#
# This file is part of GNU Radio
#
# GNU Radio is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2, or (at your option)
# any later version.
#
# GNU Radio is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with GNU Radio; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
#

_verbose = True

import math
from gnuradio import gr, gru, op25 as _op25

try:
    from gnuradio import fsk4   # LEGACY
    if _verbose:
        print "Imported legacy fsk4"
except:
    pass

# Reference code
#class decode_watcher(threading.Thread):
#    def __init__(self, msgq, traffic_pane, **kwds):
#        threading.Thread.__init__ (self, **kwds)
#        self.setDaemon(1)
#        self.msgq = msgq
#        self.keep_running = True
#        self.start()
#    def run(self):
#        while(self.keep_running):
#            msg = self.msgq.delete_head()
#            pickled_dict = msg.to_string()
#            attrs = pickle.loads(pickled_dict)
#            #update(attrs)

SYMBOL_DEVIATION = 600
SYMBOL_RATE = 4800

class op25_fsk4(gr.hier_block2):
    def __init__(self, channel_rate, auto_tune_msgq=None):
        gr.hier_block2.__init__(self, "op25_fsk4",
                              gr.io_signature(1, 1, gr.sizeof_float),
                              gr.io_signature(1, 1, gr.sizeof_float))
        
        self.symbol_rate = SYMBOL_RATE
        
        #print "Channel rate:", channel_rate
        self.channel_rate = channel_rate
        self.auto_tune_msgq = auto_tune_msgq
        
        if self.auto_tune_msgq is None:
            self.auto_tune_msgq = gr.msg_queue(2)
        
        # C4FM demodulator
        #print "Symbol rate:", self.symbol_rate
        try:
            self.demod_fsk4 = _op25.fsk4_demod_ff(self.auto_tune_msgq, self.channel_rate, self.symbol_rate)
            if _verbose:
                print "Using new fsk4_demod_ff"
        except:
            try:
                self.demod_fsk4 = fsk4.demod_ff(self.auto_tune_msgq, self.channel_rate, self.symbol_rate)   # LEGACY
                if _verbose:
                    print "Using legacy fsk4.demod_ff"
            except:
                raise Exception("Could not find a FSK4 demodulator to use")
        
        self.connect(self, self.demod_fsk4, self)

class op25_decoder_simple(gr.hier_block2):
    def __init__(self, traffic_msgq=None, key=None):
        gr.hier_block2.__init__(self, "op25_decoder",
                              gr.io_signature(1, 1, gr.sizeof_float),
                              gr.io_signature(1, 1, gr.sizeof_float))
        
        self.traffic_msgq = traffic_msgq
        self.key = key
        
        if self.traffic_msgq is None:
            self.traffic_msgq = gr.msg_queue(2)
        
        self.slicer = None
        try:
            levels = [ -2.0, 0.0, 2.0, 4.0 ]
            self.slicer = _op25.fsk4_slicer_fb(levels)
            self.p25_decoder = _op25.decoder_bf()
            self.p25_decoder.set_msgq(self.traffic_msgq)
            if _verbose:
                print "Using new decoder_bf"
        except:
            try:
                self.p25_decoder = _op25.decoder_ff(self.traffic_msgq)   # LEGACY
                if _verbose:
                    print "Using legacy decoder_ff"
            except:
                raise Exception("Could not find a decoder to use")
        
        if (self.key is not None) and (len(self.key) > 0): # Relates to key string passed in from GRC block
            self.set_key(self.key)
        
        if self.slicer:
            self.connect(self, self.slicer, self.p25_decoder)
        else:
            self.connect(self, self.p25_decoder)
        self.connect(self.p25_decoder, self)
    
    def set_key(self, key):
        try:
            if type(key) == str:
                if len(key) == 0:	# FIXME: Go back into the clear
                    #print "Cannot set key using empty string"
                    return False
                key = int(key, 16) # Convert from hex string
            if not hasattr(self.p25_decoder, 'set_key'):
                print "This version of the OP25 decoder does not support decryption"
                return False
            self.p25_decoder.set_key(key)
            return True
        except Exception, e:
            print "Exception while setting key:", e
            return False

class op25_decoder(gr.hier_block2):
    def __init__(self, channel_rate, auto_tune_msgq=None, defer_creation=False, output_dibits=False, key=None, traffic_msgq=None):
        num_outputs = 1
        if output_dibits:
            num_outputs += 1
        
        gr.hier_block2.__init__(self, "op25",
                              gr.io_signature(1, 1, gr.sizeof_float),
                              gr.io_signature(num_outputs, num_outputs, gr.sizeof_float))
        
        self.symbol_rate = SYMBOL_RATE
        
        #print "Channel rate:", channel_rate
        self.channel_rate = channel_rate
        self.auto_tune_msgq = auto_tune_msgq
        self.traffic_msgq = traffic_msgq
        self.output_dibits = output_dibits
        self.key = key
        self.traffic_msgq = gr.msg_queue(2)
        
        if defer_creation == False:
            self.create()
    
    def create(self):
        self.fsk4 = op25_fsk4(channel_rate=self.channel_rate, auto_tune_msgq=self.auto_tune_msgq)
        self.decoder = op25_decoder_simple(traffic_msgq=self.traffic_msgq, key=self.key)
        
        # Reference code
        #self.decode_watcher = decode_watcher(self.op25_msgq, self.traffic)
        
        # Reference code
        #trans_width = 12.5e3 / 2;
        #trans_centre = trans_width + (trans_width / 2)
        # discriminator tap doesn't do freq. xlation, FM demodulation, etc.
        #    coeffs = gr.firdes.low_pass(1.0, capture_rate, trans_centre, trans_width, gr.firdes.WIN_HANN)
        #    self.channel_filter = gr.freq_xlating_fir_filter_ccf(channel_decim, coeffs, 0.0, capture_rate)
        #    self.set_channel_offset(0.0, 0, self.spectrum.win._units)
        #    # power squelch
        #    squelch_db = 0
        #    self.squelch = gr.pwr_squelch_cc(squelch_db, 1e-3, 0, True)
        #    self.set_squelch_threshold(squelch_db)
        #    # FM demodulator
        #    fm_demod_gain = channel_rate / (2.0 * pi * self.symbol_deviation)
        #    fm_demod = gr.quadrature_demod_cf(fm_demod_gain)
        # symbol filter        
        #symbol_decim = 1
        #symbol_coeffs = gr.firdes.root_raised_cosine(1.0, channel_rate, self.symbol_rate, 0.2, 500)
        # boxcar coefficients for "integrate and dump" filter
        #samples_per_symbol = channel_rate // self.symbol_rate
        #symbol_duration = float(self.symbol_rate) / channel_rate
        #print "Symbol duration:", symbol_duration
        #print "Samples per symbol:", samples_per_symbol
        #symbol_coeffs = (1.0/samples_per_symbol,)*samples_per_symbol
        #self.symbol_filter = gr.fir_filter_fff(symbol_decim, symbol_coeffs)
        
        # Reference code
        #self.demod_watcher = demod_watcher(autotuneq, self.adjust_channel_offset)
        #list = [[self, self.channel_filter, self.squelch, fm_demod, self.symbol_filter, demod_fsk4, self.p25_decoder, self.sink]]
        
        self.connect(self, self.fsk4, self.decoder, (self, 0))
        
        if self.output_dibits:
            self.connect(self.fsk4, (self, 1))
    
    def set_key(self, key):
        try:
            if type(key) == str:
                if len(key) == 0:	# FIXME: Go back into the clear
                    #print "Cannot set key using empty string"
                    return False
                key = int(key, 16) # Convert from hex string
            if not hasattr(self.p25_decoder, 'set_key'):
                print "This version of the OP25 decoder does not support decryption"
                return False
            self.p25_decoder.set_key(key)
            return True
        except Exception, e:
            print "Exception while setting key:", e
            return False
    
    # Reference code
    #def adjust_channel_offset(self, delta_hz):
    #    max_delta_hz = 12000.0
    #    delta_hz *= self.symbol_deviation      
    #    delta_hz = max(delta_hz, -max_delta_hz)
    #    delta_hz = min(delta_hz, max_delta_hz)
    #    self.channel_filter.set_center_freq(self.channel_offset - delta_hz)
