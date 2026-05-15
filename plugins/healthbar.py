# plugins/healthbar.py
# Minimal, MATB-style plugin that draws a bar and updates with performance events

from plugins.abstract import AbstractPlugin
from plugins.healthbar_bus import drain_events
from core.container import Container
from core.constants import COLORS as C
from core.widgets import HealthBar

class Healthbar(AbstractPlugin):
    """
    A small bar placed near the chrono/scheduler that tracks session "health".
    Health goes down on MISS/FA, up on HIT/CORRECT, and regenerates slowly.
    """
    def __init__(self, taskplacement='invisible', taskupdatetime=80):
        super().__init__(taskplacement, taskupdatetime)

        self.parameters.update(dict(
            # Shared parameters
            max_health=100.0,
            min_health=0.0,
            start_health=100.0,
            color_good=(0, 200, 100, 225),
            color_bad=(255, 100, 100, 255),

            # System Monitoring
            sysmon_gain_hit=10.0,
            sysmon_penalty_delay=3.0,
            sysmon_penalty_miss=9.0,
            sysmon_penalty_fa=10.0,
            sysmon_regen_per_sec=0.0,
            sysmon_label='SYSTEM MONITORING',
            sysmon_font='LARGE',            # fixed duplicate key (was 'sysmon_label' twice)
            sysmon_good_color=(0, 200, 100, 225),
            sysmon_bad_color=(255, 100, 100, 255),

            # Communications
            comms_gain_correct=15.0,
            comms_penalty_delay=4.0,
            comms_penalty_fa=12.0,
            comms_penalty_miss=12.0,
            comms_regen_per_sec=0.0,
            comms_label='COMMUNICATION',
            comms_font='LARGE',
            comms_good_color=(0, 200, 100, 225),
            comms_bad_color=(255, 100, 100, 255),

            # Tracking
            track_gain_ontarget=1.0,
            track_penalty_offcenter=2.0,
            track_regen_per_sec=0.5,
            track_label='TRACK',
            track_font='LARGE',
            track_good_color=(0, 200, 100, 225),
            track_bad_color=(255, 100, 100, 255),

            # UI
            layout='horizontal',
            bar_length_ratio=0.45,
            bar_thickness_ratio=0.15,
            bar_anchor='bottomright',
            bar_margin_ratio=0.02,
            border_color=(255, 255, 255, 255),
            back_color=(40, 40, 45, 255),
            spacing_ratio=0.02,
            
        ))
        # self._health = self.parameters['start_health']
        self._health_sysmon = self.parameters['start_health']
        self._health_comms = self.parameters['start_health']
        self._health_track = self.parameters['start_health']
       

    # ---- helpers

    def _clamp(self, v):
        p = self.parameters
        return max(p['min_health'], min(p['max_health'], v))

    # ---- state handling

    def show(self):
        """Override show to ensure healthbar widget is visible"""
        super().show()
        # For invisible placement, ensure healthbar widget is shown
        for bar_key in ['healthbar_sysmon', 'healthbar_comms', 'healthbar_track']:
            widget = self.get_widget(bar_key)
            if widget is not None:
                widget.show()

    def hide(self):
        """Override hide - for invisible placement, we might want to keep widget visible"""
        # For invisible placement, don't hide the healthbar widget
        # as it provides important feedback
        if self.parameters['taskplacement'] == 'invisible':
            # Just mark plugin as not visible, but keep widget shown
            self.visible = False
            self.update_can_receive_key()
        else:
            super().hide()

    # ---- widgets

    def create_widgets(self):
        # Call parent create_widgets to set up containers
        # For invisible placement, container will be (0,0,0,0) but that's okay
        super().create_widgets()

        # Ensure window is available
        if self.win is None:
            return

        # Get layout parameters
        layout = self.parameters['layout']
        length_ratio = self.parameters['bar_length_ratio']
        thickness_ratio = self.parameters['bar_thickness_ratio']
        spacing_ratio = self.parameters['spacing_ratio']
        margin_ratio = self.parameters['bar_margin_ratio']
        anchor = self.parameters['bar_anchor']

        # Individual bar Dimensions
        if layout == 'horizontal':
            w = self.win.width * length_ratio
            h = self.win.height * thickness_ratio
        else:
            w = self.win.width * thickness_ratio
            h = self.win.height *length_ratio

        w = max(10, w)
        h = max (10, h)
        spacing = self.win.width*spacing_ratio if layout == 'horizontal' else self.win.height * spacing_ratio

        margin_x = self.win.width * margin_ratio
        margin_y = self.win.height * margin_ratio

        # Individual bar dimensions
        if layout == 'horizontal':
            total_width = 3 * w + 2 * spacing
            total_height = h 
        else: 
            total_width = w
            total_height = 3 * h + 2 * spacing

        # Starting anchor position
        if 'left' in anchor:
            start_x = margin_x
        elif 'right' in anchor:
            start_x  = self.win.width - margin_x 
        else: 
            start_x = (self.win.width - total_width)/2
        
        if 'bottom' in anchor:
            start_y = margin_y 
        elif 'top' in anchor:
            start_y = self.win.height - margin_y 
        else:
            start_y = (self.win.height - margin_y)/2

        # Define Healthbars
        bars_config = [
            {
                'key': 'healthbar_sysmon',
                'label': self.parameters['sysmon_label'],
                'good_color': self.parameters['sysmon_good_color'],
                'bad_color': self.parameters['sysmon_bad_color'],
                'font_key': self.parameters['sysmon_font'],
                'index': 0
            },
            {
                'key': 'healthbar_comms',
                'label': self.parameters['comms_label'],
                'good_color': self.parameters['comms_good_color'],
                'bad_color': self.parameters['comms_bad_color'],
                'font_key': self.parameters['comms_font'],
                'index': 1
            },
            {
                'key': 'healthbar_track',
                'label': self.parameters['track_label'],
                'good_color': self.parameters['track_good_color'],
                'bad_color': self.parameters['track_bad_color'],
                'font_key': self.parameters['track_font'],
                'index': 2
            }
        ]
        # Create health bars
        for config in bars_config:
            if layout == 'horizontal':
                x = start_x + config['index']*(w+spacing)
                y = start_y
            else:
                x = start_x 
                y = start_y + config['index'] * (h + spacing)
            
            bar_container = Container(f"container_{config['key']}", x, y, w, h)

            # create widget
            self.add_widget(config['key'], HealthBar,
                            container=bar_container, 
                            max_health=self.parameters['max_health'],
                            min_health=self.parameters['min_health'],
                            good_color=config['good_color'],
                            bad_color=config['bad_color'],
                            back_color=self.parameters['back_color'],
                            border_color=self.parameters['border_color'],
                            text_color=(255, 255, 255, 255),
                            label=config['label'],
                            label_font_key=config['font_key'],
                            value_font_key=config['font_key']
                            )
        #initialize health bars
        sysmon_widget = self.get_widget('healthbar_sysmon')
        if sysmon_widget is not None:
            sysmon_widget.set_health(self._health_sysmon)
            sysmon_widget.show()
        
        comms_widget = self.get_widget('healthbar_comms')
        if comms_widget is not None:
            comms_widget.set_health(self._health_comms)
            comms_widget.show()

        track_widget = self.get_widget('healthbar_track')
        if track_widget is not None:
            track_widget.set_health(self._health_track)
            track_widget.show()

    # ---- logic

    def compute_next_plugin_state(self):
        if super().compute_next_plugin_state() == 0:
            return

        # 1) Apply regen
        dt_s = self.parameters['taskupdatetime'] / 1000.0
        self._health_sysmon = self._clamp(self._health_sysmon + self.parameters['sysmon_regen_per_sec'] * dt_s)
        self._health_comms = self._clamp(self._health_comms + self.parameters['comms_regen_per_sec'] * dt_s)
        self._health_track = self._clamp(self._health_track + self.parameters['track_regen_per_sec'] * dt_s)


        # 2) Consume performance events posted by other plugins
        for _, k, source, value in drain_events():
            # System monitoring events
            if k == 'HIT':
                # Sysmon correct response: +10
                self._health_sysmon = self._clamp(self._health_sysmon + self.parameters['sysmon_gain_hit'])
            
            elif k in ('SYSMON_DELAY_1', 'SYSMON_DELAY_2', 'SYSMON_DELAY_3', 'SYSMON_DELAY_4'):
                # Sysmon delay penalty: -3 each
                self._health_sysmon = self._clamp(self._health_sysmon - self.parameters['sysmon_penalty_delay'])
            
            elif k == 'MISS':
                # Sysmon final timeout: -9
                self._health_sysmon = self._clamp(self._health_sysmon - self.parameters['sysmon_penalty_miss'])
            
            elif k == 'FA':
                # Sysmon false alarm: -10
                self._health_sysmon = self._clamp(self._health_sysmon - self.parameters['sysmon_penalty_fa'])
            
           # Communications events
            elif k == 'CORRECT':
                # Communications correct frequency: +15
                self._health_comms = self._clamp(self._health_comms + self.parameters['comms_gain_correct'])
            
            elif k in ('COMMS_DELAY_1', 'COMMS_DELAY_2', 'COMMS_DELAY_3', 'COMMS_DELAY_4'):
                # Communications delay penalty: -4 each
                self._health_comms = self._clamp(self._health_comms - self.parameters['comms_penalty_delay'])
            
            elif k in ('BAD_FREQ', 'BAD_RADIO', 'BAD_RADIO_FREQ', 'COMMS_FA'):
                # Communications wrong frequency/radio or false alarm: -12
                self._health_comms = self._clamp(self._health_comms - self.parameters['comms_penalty_fa'])
            
            elif k == 'COMMS_MISS':
                # Communications final timeout: -12
                self._health_comms = self._clamp(self._health_comms - self.parameters['comms_penalty_miss'])
            
            # Tracking events
            elif k == 'TRACK_ONTARGET':
                # Tracking cursor on-target: +1 every 500ms
                self._health_track = self._clamp(self._health_track + self.parameters['track_gain_ontarget'])
            
            elif k == 'TRACK_OFFCENTER':
                # Tracking cursor off-target: -2 every 500ms
                self._health_track = self._clamp(self._health_track - self.parameters['track_penalty_offcenter'])


    def refresh_widgets(self):
        # Update healthbar widget first, before parent's visibility check
        sysmon_widget = self.get_widget('healthbar_sysmon')
        if sysmon_widget is not None:
            sysmon_widget.set_health(self._health_sysmon)
        
        comms_widget = self.get_widget('healthbar_comms')
        if comms_widget is not None:
            comms_widget.set_health(self._health_comms)
        
        track_widget = self.get_widget ('healthbar_track')
        if track_widget is not None:
            track_widget.set_health(self._health_track)

        was_visible = self.visible 
        if self.parameters['taskplacement'] == 'invisible' and self.alive:
            self.visible = True
        
        result = super().refresh_widgets()

        if self.parameters['taskplacement'] == 'invisible':
            self.visible = was_visible if not self.alive else True
        
        return result if result != 0 else 1