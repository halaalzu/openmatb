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

        # Tunables (you can tweak live via scenario or parameters)
        self.parameters.update(dict(
            max_health=100.0,
            start_health=100.0,
            regen_per_sec=0.0,        # passive regen
            gain_hit=6.0,             # HIT from sysmon, etc.
            gain_correct=10.0,         # exact correct actions (e.g., comms tuned)
            penalty_miss=12.0,        # MISS (timeout)
            penalty_fa=10.0,           # false alarm / wrong key
            min_health=0.0,

            # UI sizing/colors - improved appearance
            orientation='vertical',
            bar_length_ratio=0.4,    # Portion of screen height for bar length
            bar_thickness_ratio=0.08,  # Thicker, more visible
            bar_anchor='bottomright', # Align to screen corner
            bar_margin_ratio=0.025,    # Margin from screen edges
            border_color=(255, 255, 255, 255),  # Bright white border
            good_color=(100, 255, 150, 255),   # Bright green at high health
            bad_color=(255, 80, 80, 255),       # Bright red at low health
            back_color=(40, 40, 45, 255),      # Dark background with slight blue tint
            text_color=(C['BLACK']),   # White text
            label='HEALTH',
            label_font='LARGE',       # Larger font for visibility
            value_font='LARGE'
        ))

        self._health = self.parameters['start_health']

    # ---- helpers

    def _clamp(self, v):
        p = self.parameters
        return max(p['min_health'], min(p['max_health'], v))

    # ---- state handling

    def show(self):
        """Override show to ensure healthbar widget is visible"""
        super().show()
        # For invisible placement, ensure healthbar widget is shown
        healthbar_widget = self.get_widget('healthbar')
        if healthbar_widget is not None:
            healthbar_widget.show()

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

        orientation = self.parameters['orientation']
        length_ratio = self.parameters['bar_length_ratio']
        thickness_ratio = self.parameters['bar_thickness_ratio']

        if orientation == 'vertical':
            w = self.win.width * thickness_ratio
            h = self.win.height * length_ratio
        else:
            w = self.win.width * length_ratio
            h = self.win.height * thickness_ratio

        w = max(10, w)
        h = max(10, h)

        anchor = self.parameters['bar_anchor']
        margin_ratio = self.parameters['bar_margin_ratio']
        margin_x = self.win.width * margin_ratio
        margin_y = self.win.height * margin_ratio

        if 'left' in anchor:
            x = margin_x
        elif 'right' in anchor:
            x = self.win.width - w - margin_x
        else:  # center horizontally
            x = (self.win.width - w) / 2

        if 'bottom' in anchor:
            y = margin_y
        elif 'top' in anchor:
            y = self.win.height - h - margin_y
        else:  # center vertically
            y = (self.win.height - h) / 2

        bar_container = Container('healthbar_bar', x, y, w, h)

        # Create the healthbar widget
        self.add_widget('healthbar', HealthBar,
                        container=bar_container,
                        max_health=self.parameters['max_health'],
                        min_health=self.parameters['min_health'],
                        good_color=self.parameters['good_color'],
                        bad_color=self.parameters['bad_color'],
                        back_color=self.parameters['back_color'],
                        border_color=self.parameters['border_color'],
                        text_color=self.parameters['text_color'],
                        label=self.parameters['label'],
                        orientation=orientation,
                        label_font_key=self.parameters['label_font'],
                        value_font_key=self.parameters['value_font'])

        # Initialize health and show the widget
        healthbar_widget = self.get_widget('healthbar')
        if healthbar_widget is not None:
            healthbar_widget.set_health(self._health)
            healthbar_widget.show()

    # ---- logic

    def compute_next_plugin_state(self):
        if super().compute_next_plugin_state() == 0:
            return

        # 1) Apply regen
        dt_s = self.parameters['taskupdatetime'] / 1000.0
        self._health = self._clamp(self._health + self.parameters['regen_per_sec'] * dt_s)

        # 2) Consume performance events posted by other plugins
        for _, kind, source, value in drain_events():
            k = (kind or '').upper()
            if k in ('HIT', 'CORRECT'):
                delta = self.parameters['gain_hit'] if k == 'HIT' else self.parameters['gain_correct']
                self._health = self._clamp(self._health + delta)
            elif k in ('MISS', 'FA'):
                delta = self.parameters['penalty_miss'] if k == 'MISS' else self.parameters['penalty_fa']
                self._health = self._clamp(self._health - delta)
            # You can optionally map BAD_FREQ/BAD_RADIO/etc.:
            elif k in ('BAD_FREQ', 'BAD_RADIO', 'BAD_RADIO_FREQ'):
                self._health = self._clamp(self._health - (self.parameters['penalty_fa'] * 0.75))
            elif k == 'COMMS_MISS':
                self._health = self._clamp(self._health - (self.parameters['penalty_miss'] * 1.5))

    def refresh_widgets(self):
        # Update healthbar widget first, before parent's visibility check
        # This ensures it updates even for invisible placement
        healthbar_widget = self.get_widget('healthbar')
        if healthbar_widget is not None:
            healthbar_widget.set_health(self._health)
        
        # For invisible placement, ensure plugin is considered visible so parent refreshes
        # This allows the plugin to update even though it uses invisible placement
        was_visible = self.visible
        if self.parameters['taskplacement'] == 'invisible' and self.alive:
            self.visible = True
        
        # Call parent refresh_widgets
        result = super().refresh_widgets()
        
        # Restore visibility state for invisible placement
        if self.parameters['taskplacement'] == 'invisible':
            self.visible = was_visible if not self.alive else True
        
        return result if result != 0 else (1 if healthbar_widget is not None else 0)
