from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class SimConfig(BaseModel):
    tick_seconds: float = 1.0
    max_ticks: int = 400
    robbery_duration: int = 20


class MapConfig(BaseModel):
    rows: int = 7
    cols: int = 7
    block_m: float = 120.0
    jitter: float = 0.15
    removal_prob: float = 0.12
    n_exits: int = 4
    arterials: int = 2


class PoliceConfig(BaseModel):
    count: int = 4
    speed: float = 15.0
    report_interval: int = 2
    replan_threshold: float = 0.2
    capture_radius_m: float = 14.0


class RobberConfig(BaseModel):
    speed: float = 13.0
    vision_radius_m: float = 200.0
    temperature: float = 0.3
    danger_lambda: float = 3.0
    threat_radius_m: float = 150.0
    cooldown_ticks: int = 5
    memory_ticks: int = 10


class CiviliansConfig(BaseModel):
    count: int = 25
    speed: float = 7.0


class CCTVConfig(BaseModel):
    count: int = 5
    placement: Literal["chokepoints", "random", "bank_ring"] = "chokepoints"
    range_m: float = 150.0
    p_detect_max: float = 0.9
    noise_sigma_m: float = 15.0


class AlarmConfig(BaseModel):
    probability: float = 1.0
    delay_min: int = 1
    delay_max: int = 1


class SurveillanceConfig(BaseModel):
    zones: int = 1
    detection_threshold: float = 0.7


class TrafficConfig(BaseModel):
    base: float = 1.0
    civilian_factor: float = 0.05
    jam_rate: float = 0.01
    jam_severity: float = 1.5
    jam_min: int = 30
    jam_max: int = 90


class CommandConfig(BaseModel):
    top_k_routes: int = 3
    horizon_s: float = 120.0
    safety_buffer_s: float = 3.0
    switch_gain: float = 0.15
    min_route_prob: float = 0.1


class ScenarioConfig(BaseModel):
    name: str = "Default"
    description: str = ""
    seed: int | None = None
    sim: SimConfig = Field(default_factory=SimConfig)
    map: MapConfig = Field(default_factory=MapConfig)
    police: PoliceConfig = Field(default_factory=PoliceConfig)
    robber: RobberConfig = Field(default_factory=RobberConfig)
    civilians: CiviliansConfig = Field(default_factory=CiviliansConfig)
    cctv: CCTVConfig = Field(default_factory=CCTVConfig)
    alarm: AlarmConfig = Field(default_factory=AlarmConfig)
    surveillance: SurveillanceConfig = Field(default_factory=SurveillanceConfig)
    traffic: TrafficConfig = Field(default_factory=TrafficConfig)
    command: CommandConfig = Field(default_factory=CommandConfig)
